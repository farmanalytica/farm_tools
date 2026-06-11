# -*- coding: utf-8 -*-
"""
GEE (Google Earth Engine) service layer.

All Earth Engine business logic lives here, keeping the UI layer free
of SDK-specific details.
"""

import json
import os
import time

import ee
from qgis.PyQt.QtCore import QCoreApplication, QSettings


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


class AuthCancelled(Exception):
    """Raised when the user aborts the OAuth flow before it completes."""


class AuthTimeout(Exception):
    """Raised when the browser sign-in is not completed within the deadline."""


class GEEService:
    """
    Service layer for Google Earth Engine operations.

    Handles authentication, initialization, and credential management
    for the Google Earth Engine API.
    """

    SETTINGS_PROJECT_ID_KEY = "MyPlugin/projectID"
    SETTINGS_AUTH_MODE_KEY = "MyPlugin/authMode"
    SETTINGS_SA_KEY_PATH_KEY = "MyPlugin/serviceAccountKeyPath"

    MODE_PERSONAL = "personal"
    MODE_SERVICE = "service"

    def __init__(self):
        self.is_authenticated = False

    def has_stored_credentials(self) -> bool:

        try:
            return os.path.exists(ee.oauth.get_credentials_path())
        except Exception:
            return False

    def check_silent_auth(self, project_id: str) -> bool:
        """Check authentication without ever launching the browser OAuth flow"""

        if not project_id or not self.has_stored_credentials():
            self.is_authenticated = False
            return False

        try:
            ee.Initialize(project=project_id)
            ee.data.listAssets({"parent": f"projects/{project_id}/assets/"})
            self.is_authenticated = True
            return True
        except Exception:
            self.is_authenticated = False
            return False

    def get_saved_project_id(self) -> str:
        return QSettings().value(self.SETTINGS_PROJECT_ID_KEY, "", type=str)

    def save_project_id(self, project_id) -> None:
        QSettings().setValue(self.SETTINGS_PROJECT_ID_KEY, project_id)

    # --- Service-account credentials --------------------------------------

    def get_saved_auth_mode(self) -> str:
        mode = QSettings().value(self.SETTINGS_AUTH_MODE_KEY, self.MODE_PERSONAL, type=str)
        return mode if mode in (self.MODE_PERSONAL, self.MODE_SERVICE) else self.MODE_PERSONAL

    def save_auth_mode(self, mode: str) -> None:
        QSettings().setValue(self.SETTINGS_AUTH_MODE_KEY, mode)

    def get_saved_sa_key_path(self) -> str:
        return QSettings().value(self.SETTINGS_SA_KEY_PATH_KEY, "", type=str)

    def save_sa_key_path(self, path: str) -> None:
        # Persist only the path so later sessions can re-authenticate silently;
        # the key contents themselves are never copied or stored by the plugin.
        QSettings().setValue(self.SETTINGS_SA_KEY_PATH_KEY, path)

    def clear_sa_key_path(self) -> None:
        QSettings().remove(self.SETTINGS_SA_KEY_PATH_KEY)

    @staticmethod
    def read_service_account_key(key_path: str) -> dict:
        """Parse a service-account JSON key, returning its decoded fields.

        Raises ValueError if the file is missing, unreadable, or not a
        recognisable service-account key (no ``client_email``).
        """
        try:
            with open(key_path, "r", encoding="utf-8") as fh:
                info = json.load(fh)
        except FileNotFoundError:
            raise ValueError(_tr("Key file not found."))
        except (OSError, json.JSONDecodeError):
            raise ValueError(_tr("Could not read the key file as JSON."))

        if not isinstance(info, dict) or not info.get("client_email"):
            raise ValueError(_tr("Not a valid service-account key file."))
        return info

    def extract_project_id_from_key(self, key_path: str) -> str:
        """Best-effort read of ``project_id`` from a service-account key.

        Returns an empty string if the file cannot be parsed; callers use this
        only to pre-fill the editable Project ID field.
        """
        try:
            return self.read_service_account_key(key_path).get("project_id", "")
        except ValueError:
            return ""

    def _build_sa_credentials(self, key_path: str):
        info = self.read_service_account_key(key_path)
        return ee.ServiceAccountCredentials(info["client_email"], key_file=key_path)

    def check_silent_sa_auth(self, key_path: str, project_id: str) -> bool:
        """Authenticate with a service-account key without any user prompt."""
        if not key_path or not os.path.exists(key_path) or not project_id:
            self.is_authenticated = False
            return False
        try:
            ee.Initialize(self._build_sa_credentials(key_path), project=project_id)
            ee.data.listAssets({"parent": f"projects/{project_id}/assets/"})
            self.is_authenticated = True
            return True
        except Exception:
            self.is_authenticated = False
            return False

    def authenticate_service_account(self, key_path: str, project_id: str):
        """Initialise Earth Engine from a service-account JSON key.

        Unlike the OAuth flow this never opens a browser, so it runs to
        completion synchronously; the worker only keeps it off the UI thread.
        """
        try:
            credentials = self._build_sa_credentials(key_path)
            ee.Initialize(credentials, project=project_id)
            ee.data.listAssets({"parent": f"projects/{project_id}/assets/"})
            self.is_authenticated = True
        except ValueError as e:
            raise Exception(str(e))
        except ee.EEException as e:
            raise Exception(
                _tr("Service-account authentication failed: {0}").format(str(e))
            )
        except Exception as e:
            raise Exception(_tr("An unexpected error occurred: {0}").format(str(e)))

    def authenticate(
        self,
        project_id: str,
        timeout: float = 180,
        should_cancel=None,
        on_browser_open=None,
    ):

        should_cancel = should_cancel or (lambda: False)
        try:
            try:
                ee.Initialize(project=project_id)

            except ee.EEException:
                self._run_local_auth_flow(timeout, should_cancel, on_browser_open)
                ee.Initialize(project=project_id)

            default_project_path = f"projects/{project_id}/assets/"

            ee.data.listAssets({"parent": default_project_path})
            self.is_authenticated = True

        except (AuthCancelled, AuthTimeout):
            raise

        except ee.EEException as e:
            error_msg = str(e)

            if "Earth Engine client library not initialized" in error_msg:
                raise Exception("Authentication failed. Please authenticate again.")
            else:
                raise Exception(
                    f"An error occurred during authentication or initialization: {error_msg}"
                )

        except Exception as e:
            raise Exception(f"An unexpected error occurred: {e}")

    def _run_local_auth_flow(self, timeout, should_cancel, on_browser_open):
        """Run the GEE localhost OAuth flow with a bounded, cancellable wait"""
        from ee import oauth

        flow = oauth.Flow("localhost", oauth.SCOPES)
        local_server = flow.server.server
        try:
            oauth._open_new_browser(flow.auth_url)
            if on_browser_open:
                on_browser_open(flow.auth_url)

            local_server.timeout = 1.0
            request_handler = local_server.RequestHandlerClass
            deadline = time.monotonic() + timeout
            auth_code = None
            while not auth_code:
                if should_cancel():
                    raise AuthCancelled()
                if time.monotonic() > deadline:
                    raise AuthTimeout()
                local_server.handle_request()
                auth_code = getattr(request_handler, "code", None)
        finally:
            try:
                local_server.server_close()
            except Exception:
                pass

        oauth._obtain_and_write_token(
            auth_code, flow.code_verifier, flow.scopes, flow.server.url
        )

    def reset_authentication(self):

        credentials_path = ee.oauth.get_credentials_path()
        had_oauth = os.path.exists(credentials_path)
        had_sa = bool(self.get_saved_sa_key_path())

        if not had_oauth and not had_sa:
            raise FileNotFoundError(
                _tr("No Earth Engine configuration found to clear.")
            )

        if had_oauth:
            os.remove(credentials_path)

        # Forget the service-account key path so it no longer auto-authenticates.
        # The key file on disk is never touched — only the saved pointer.
        self.clear_sa_key_path()

        try:
            import importlib

            importlib.reload(ee.oauth)
            ee.Reset()
        except Exception:
            pass

        self.is_authenticated = False
        return _tr("Earth Engine configuration cleared successfully.")
