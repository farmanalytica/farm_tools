# -*- coding: utf-8 -*-
import os
import re

from qgis.PyQt.QtCore import QCoreApplication, QTimer
from qgis.PyQt.QtWidgets import QFileDialog

from ..workers.auth_worker import AuthWorker, AuthStatusWorker, CANCELLED
from ..managers.settings_manager import SettingsManager


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


class AuthCtrl:
    """Handles all user interactions on the authentication page."""

    _STATUS_TIMEOUT_MS = 12000
    _PROJECT_ID_RE = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")

    def __init__(self, dialog, gee_service):
        self.dialog = dialog
        self.gee_service = gee_service

        self._auth_worker: AuthWorker | None = None
        self._status_worker: AuthStatusWorker | None = None
        self._status_timer = QTimer(dialog)
        self._status_timer.setSingleShot(True)
        self._status_timer.setInterval(self._STATUS_TIMEOUT_MS)
        self._status_timer.timeout.connect(self._on_status_timeout)

    def _current_mode(self) -> str:
        return (
            self.gee_service.MODE_SERVICE
            if self.dialog.btn_mode_service.isChecked()
            else self.gee_service.MODE_PERSONAL
        )

    def _credential_state(self) -> str:
        if self._current_mode() == self.gee_service.MODE_SERVICE:
            key_path = self.gee_service.get_saved_sa_key_path()
            return "stored" if key_path and os.path.exists(key_path) else "none"
        return "stored" if self.gee_service.has_stored_credentials() else "none"

    def _is_busy(self) -> bool:
        return (self._auth_worker is not None and self._auth_worker.isRunning()) or (
            self._status_worker is not None and self._status_worker.isRunning()
        )

    def _cleanup_worker(self, worker):
        worker.deleteLater()

    def refresh_auth_status(self):

        if self._is_busy():
            return

        if self.gee_service.is_authenticated:
            self.dialog.set_auth_state("authenticated")
            return

        self.dialog.set_auth_state("checking")

        sa_key_path = (
            self.gee_service.get_saved_sa_key_path()
            if self._current_mode() == self.gee_service.MODE_SERVICE
            else None
        )
        self._status_worker = AuthStatusWorker(
            self.gee_service,
            self.dialog.project_id_input.text(),
            sa_key_path=sa_key_path,
        )
        self._status_worker.status_ready.connect(self._on_status_ready)
        self._status_worker.finished.connect(self._on_status_finished)
        self._status_worker.start()
        self._status_timer.start()

    def _on_status_ready(self, state: str):

        self._status_timer.stop()
        self.dialog.set_auth_state(self._authenticated_state(state))

    def _authenticated_state(self, state: str) -> str:
        """Map a worker 'authenticated' result to the mode-specific badge."""
        if state != "authenticated":
            return state
        if self._current_mode() == self.gee_service.MODE_SERVICE:
            return "authenticated_sa"
        return "authenticated"

    def _on_status_timeout(self):

        if self.gee_service.is_authenticated:
            self.dialog.set_auth_state(self._authenticated_state("authenticated"))
            return

        self.dialog.set_auth_state(self._credential_state())

    def _on_status_finished(self):

        worker, self._status_worker = self._status_worker, None
        if worker:
            self._cleanup_worker(worker)

    def on_project_id_changed(self):

        if self.gee_service.is_authenticated:
            self.gee_service.is_authenticated = False
            self.dialog.set_auth_state(self._credential_state())

    def handle_authentication(self):

        if self._auth_worker is not None and self._auth_worker.isRunning():
            self._auth_worker.cancel()
            self.dialog.set_auth_status(_tr("Cancelling…"))
            return

        if self.gee_service.is_authenticated:
            self._navigate_to_next()
            return

        project_id = self.dialog.project_id_input.text()
        if not self._validate_project_id(project_id):
            return

        sa_key_path = None
        if self._current_mode() == self.gee_service.MODE_SERVICE:
            sa_key_path = self.gee_service.get_saved_sa_key_path()
            if not sa_key_path or not os.path.exists(sa_key_path):
                self.dialog.pop_message(
                    _tr("Select a service-account key file first."), "warning"
                )
                return

        self.dialog.set_auth_busy(True)
        self._auth_worker = AuthWorker(
            self.gee_service, project_id, sa_key_path=sa_key_path
        )
        self._auth_worker.browser_opened.connect(self._on_browser_opened)
        self._auth_worker.finished_auth.connect(self._on_auth_finished)
        self._auth_worker.start()

    def _validate_project_id(self, project_id: str) -> bool:
        if not project_id:
            self.dialog.pop_message(_tr("Missing Project ID."), "warning")
        if not self._PROJECT_ID_RE.match(project_id):
            self.dialog.pop_message(_tr("Invalid Project ID."), "warning")
            return False
        return True

    def _navigate_to_next(self):
        self.dialog.show_optical_page()

    def _on_browser_opened(self, url: str):
        self.dialog.set_auth_status(_tr("Waiting for sign-in in your browser…"), url)

    def _on_auth_finished(self, success: bool, message: str):
        self.dialog.set_auth_busy(False)
        worker, self._auth_worker = self._auth_worker, None
        if worker:
            self._cleanup_worker(worker)

        if success:
            self.dialog.set_auth_state(self._authenticated_state("authenticated"))
            self._navigate_to_next()
            self.dialog.pop_message(_tr("Authentication successful!"), "info")
        elif message != CANCELLED:
            self.dialog.pop_message(message, "warning")

    def handle_reset_authentication(self):
        try:
            msg = self.gee_service.reset_authentication()
            if msg:
                self.dialog.sa_key_input.clear()
                self.dialog.pop_message(msg, "info")
        except (FileNotFoundError, RuntimeError, OSError) as e:
            self.dialog.pop_message(str(e), "warning")
        finally:
            self.refresh_auth_status()

    def handle_auth_mode_changed(self, mode: str):
        """React to the personal/service segmented toggle."""
        # Always sync the card to the toggle: the QButtonGroup has already
        # flipped the checked state, so skipping set_auth_mode here would leave
        # the service-account row visible (or hidden) out of step with the mode.
        self.gee_service.save_auth_mode(mode)
        self.dialog.set_auth_mode(mode)
        if self._is_busy():
            return
        # The active credential context differs per mode, so drop any cached
        # session and re-check from scratch.
        self.gee_service.is_authenticated = False
        self.refresh_auth_status()

    def handle_browse_key(self):
        start_dir = ""
        saved = self.gee_service.get_saved_sa_key_path()
        if saved:
            start_dir = os.path.dirname(saved)

        path, _ = QFileDialog.getOpenFileName(
            self.dialog,
            _tr("Select service-account key file"),
            start_dir,
            _tr("JSON key files (*.json);;All files (*)"),
        )
        if not path:
            return

        try:
            self.gee_service.read_service_account_key(path)
        except ValueError as e:
            self.dialog.pop_message(str(e), "warning")
            return

        # Persist only the path; auto-authenticates on later sessions.
        self.gee_service.save_sa_key_path(path)
        self.dialog.sa_key_input.setText(path)

        # Pre-fill the (editable) Project ID from the key's project_id field.
        project_id = self.gee_service.extract_project_id_from_key(path)
        if project_id:
            self.dialog.project_id_input.setText(project_id)

        self.gee_service.is_authenticated = False
        self.refresh_auth_status()

    def handle_folder_selection(self):
        folder = QFileDialog.getExistingDirectory(
            self.dialog,
            _tr("Select download folder"),
            SettingsManager.load_download_folder(),
        )
        if folder:
            self.dialog.folder_input.setText(folder)
            SettingsManager.save_download_folder(folder)

    def handle_clear_folder(self):
        self.dialog.folder_input.clear()
        SettingsManager.clear_download_folder()
