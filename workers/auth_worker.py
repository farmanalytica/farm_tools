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

# The sign-in states the auth page's status pill understands.
STATE_AUTHENTICATED = "authenticated"
STATE_STORED = "stored"
STATE_NONE = "none"
STATE_AUTHENTICATED_SA = "authenticated_sa"
STATE_CHECKING = "checking"

# A browser sign-in the user never finishes should not hold the thread forever.
_AUTH_TIMEOUT_S = 180


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


class AuthWorker(QThread):
    """Manage the EE authentication flow on browser without locking the UI"""

    browser_opened = pyqtSignal(str)
    finished_auth = pyqtSignal(bool, str)

    def __init__(self, gee_service, project_id, sa_key_path=None):
        super().__init__()
        self._gee = gee_service
        self._project_id = project_id
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
                    timeout=_AUTH_TIMEOUT_S,
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
            self.status_ready.emit(self._resolve_state())
        except Exception:
            # A status check that itself fails tells us nothing new; report the
            # credentials as merely stored rather than claiming a signed-in state.
            self.status_ready.emit(STATE_STORED)

    def _resolve_state(self):
        if self._sa_key_path:
            return self._service_account_state()
        return self._user_account_state()

    def _service_account_state(self):
        """A saved key path is itself the stored state; only a project can confirm it."""
        if not self._project_id:
            return STATE_STORED
        if self._gee.check_silent_sa_auth(self._sa_key_path, self._project_id):
            return STATE_AUTHENTICATED
        return STATE_STORED

    def _user_account_state(self):
        if not self._gee.has_stored_credentials():
            return STATE_NONE
        if not self._project_id:
            return STATE_STORED
        if self._gee.check_silent_auth(self._project_id):
            return STATE_AUTHENTICATED
        return STATE_STORED
