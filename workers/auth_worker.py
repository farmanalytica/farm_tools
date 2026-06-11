# -*- coding: utf-8 -*-
"""
Background worker for Google Earth Engine authentication.

Runs the (potentially long, browser-driven) auth flow off the UI thread so
the dialog stays responsive, and exposes a ``cancel()`` so an abandoned
sign-in can be aborted instead of freezing the plugin.
"""

from qgis.PyQt.QtCore import QCoreApplication, QThread, pyqtSignal

from ..services.gee_service import AuthCancelled, AuthTimeout

CANCELLED = "__cancelled__"


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


class AuthWorker(QThread):
    """Manage the EE authentication flow on browser without locking the UI"""

    browser_opened = pyqtSignal(str)
    finished_auth = pyqtSignal(bool, str)

    def __init__(self, gee_service, project_id, timeout=180, sa_key_path=None):
        super().__init__()
        self._gee = gee_service
        self._project_id = project_id
        self._timeout = timeout
        self._sa_key_path = sa_key_path
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            if self._sa_key_path:
                # Service-account flow: no browser, runs synchronously.
                self._gee.authenticate_service_account(
                    self._sa_key_path, self._project_id
                )
            else:
                self._gee.authenticate(
                    self._project_id,
                    timeout=self._timeout,
                    should_cancel=lambda: self._is_cancelled,
                    on_browser_open=self.browser_opened.emit,
                )
            self.finished_auth.emit(True, "")
        except AuthCancelled:
            self.finished_auth.emit(False, CANCELLED)
        except AuthTimeout:
            self.finished_auth.emit(False, _tr("Sign-in timed out. Please try again."))
        except Exception as e:  # noqa: BLE001 - surface any failure to the UI
            self.finished_auth.emit(False, str(e))


class AuthStatusWorker(QThread):
    """Check of the current sign-in status"""

    status_ready = pyqtSignal(str)

    def __init__(self, gee_service, project_id, sa_key_path=None):
        super().__init__()
        self._gee = gee_service
        self._project_id = (project_id or "").strip()
        self._sa_key_path = (sa_key_path or "").strip()

    def run(self):
        try:
            if self._sa_key_path:
                # Service-account mode: a saved key path is the stored state.
                if not self._project_id:
                    self.status_ready.emit("stored")
                elif self._gee.check_silent_sa_auth(self._sa_key_path, self._project_id):
                    self.status_ready.emit("authenticated")
                else:
                    self.status_ready.emit("stored")
                return

            if not self._gee.has_stored_credentials():
                self.status_ready.emit("none")
            elif not self._project_id:
                self.status_ready.emit("stored")
            elif self._gee.check_silent_auth(self._project_id):
                self.status_ready.emit("authenticated")
            else:
                self.status_ready.emit("stored")
        except Exception:
            self.status_ready.emit("stored")
