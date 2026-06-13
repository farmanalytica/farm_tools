# Auth — Features & Methodology

The Auth page is the plugin's gateway to **Google Earth Engine (GEE)**: every
other GEE-backed module (DEM, Optical, SAR, Landsat, SYSI, MapBiomas) depends on
the Earth Engine session this page establishes. It supports **two sign-in
modes** — *personal* OAuth (interactive, browser-driven) and *service account*
(a `.json` key file, no browser) — toggled by a segmented control. Successful
sign-in initializes `ee` against the **high-volume endpoint** and advances the
dialog to the next page.

The page is deliberately thin on persistence: it stores the **Project ID**, the
chosen **auth mode**, and (for service accounts) the **path** to the key file —
never the credential contents themselves. OAuth tokens are written and managed
by the Earth Engine SDK in its own credentials store; the plugin only checks for
and deletes that store, it never reads its contents.

Code map:

| Layer | File | Responsibility |
|---|---|---|
| View | `view/auth.py` | Builds the sign-in card: mode toggle, status badge, SA key picker, Project ID field, buttons |
| Dialog | `farm_tools_dialog.py` | `set_auth_state` / `set_auth_mode` / `set_auth_busy` / `set_auth_status` — pill, card visibility, button text |
| Controller | `controllers/auth_ctrl.py` | UI orchestration, worker lifecycle, validation, status timeout |
| Workers | `workers/auth_worker.py` | `AuthWorker` (sign-in) and `AuthStatusWorker` (silent status check) run off the UI thread |
| Service | `services/gee_service.py` | All Earth Engine logic: initialize, OAuth flow, SA credentials, credential storage, reset |
| Wiring | `farm_tools.py` | Constructs `AuthCtrl`, restores saved state, connects signals, kicks off the first status check |

---

## 0. Architecture & threading

**What it does.** Authentication is potentially slow and blocking — an OAuth
flow waits on a browser round-trip, and even a "silent" check makes a network
call (`ee.data.listAssets`). Both run inside `QThread` workers so the dialog
never freezes; the controller mediates between the workers and the view.

**Methodology.**
- `ee` is imported at module top in `gee_service.py`; the service layer keeps all
  SDK-specific details out of the view and controller.
- Two distinct workers, both `QThread`:
  - `AuthWorker` runs the actual sign-in (`browser_opened`, `finished_auth(bool, str)` signals).
  - `AuthStatusWorker` runs a non-interactive status probe (`status_ready(str)` signal).
- The controller guards re-entrancy with `_is_busy()` — it refuses to start a new
  status check while either worker is still running, and the *same* primary
  button both starts and cancels the auth worker.
- Earth Engine is initialized against the **high-volume endpoint**
  (`earthengine-highvolume.googleapis.com`) in every code path, matching the rest
  of the plugin so the established session is ready for the parallel fan-out the
  other pages perform.

## 1. Two sign-in modes

**What it does.** A segmented toggle (`btn_mode_personal` / `btn_mode_service`,
an exclusive `QButtonGroup`) picks between personal OAuth and a service-account
key file. The service-account key row (`sa_key_row`) is shown only in service
mode; the Project ID field is shared by both.

**Methodology.**
- The controller derives the active mode from which toggle button is checked
  (`_current_mode()` → `MODE_PERSONAL` / `MODE_SERVICE`).
- `handle_auth_mode_changed(mode)` persists the new mode (`save_auth_mode`), syncs
  the card via `set_auth_mode`, then — because the credential context differs per
  mode — **drops the cached session** (`is_authenticated = False`) and re-runs the
  status check from scratch.
- The chosen mode is persisted in `QSettings` (`MyPlugin/authMode`) so the card
  reopens in the user's last context on the next session.

## 2. Credential storage (what is and isn't saved)

**What it does.** The plugin persists only pointers and identifiers, never secret
material it owns. Three `QSettings` keys hold all state: the Project ID, the auth
mode, and the service-account key **path**.

**Methodology.**
- `QSettings` keys: `MyPlugin/projectID`, `MyPlugin/authMode`,
  `MyPlugin/serviceAccountKeyPath`.
- **Personal mode.** OAuth tokens live wherever the EE SDK puts them
  (`ee.oauth.get_credentials_path()`); the plugin only tests for that file's
  existence (`has_stored_credentials`) and deletes it on reset. It never reads or
  copies the token.
- **Service-account mode.** Only the *path* to the user's `.json` key is saved
  (`save_sa_key_path`); the key contents are never copied or stored. The key file
  on disk is the user's, and reset only forgets the saved path
  (`clear_sa_key_path`) — it never deletes the file.
- The Project ID is validated against `^[a-z][a-z0-9-]{4,28}[a-z0-9]$` before any
  sign-in (`_validate_project_id`); it is also saved live on every keystroke
  (`textChanged → save_project_id`).

## 3. Startup & silent re-authentication

**What it does.** On dialog construction the plugin restores the saved Project
ID, key path, and mode, then immediately attempts a **silent** status check so a
returning user lands on a "Signed in & ready" pill without clicking anything.

**Methodology.**
- `farm_tools._finish_init` pre-fills `project_id_input` / `sa_key_input` from
  `QSettings`, calls `set_auth_mode(get_saved_auth_mode())`, wires all signals,
  and finally calls `auth_ctrl.refresh_auth_status()`.
- `refresh_auth_status()` short-circuits to `"authenticated"` if a session is
  already cached; otherwise it shows the `"checking"` pill and launches an
  `AuthStatusWorker`.
- The worker never opens a browser. It branches on mode:
  - **Service:** no Project ID → `"stored"`; otherwise `check_silent_sa_auth`
    (build SA credentials, `ee.Initialize`, probe `listAssets`) → `"authenticated"`
    or `"stored"`.
  - **Personal:** no stored credentials → `"none"`; no Project ID → `"stored"`;
    otherwise `check_silent_auth` (`ee.Initialize` + `listAssets`) →
    `"authenticated"` or `"stored"`.
  - Any exception degrades gracefully to `"stored"`.
- A successful "authenticated" result is mapped to a mode-specific badge:
  service mode shows `authenticated_sa` ("Signed in via service account"),
  personal shows `authenticated` (`_authenticated_state`).

## 4. Status-check timeout

**What it does.** A silent check can hang on a slow network. A 12-second
`QTimer` bounds the wait so the pill never gets stuck on "Checking…".

**Methodology.**
- `_STATUS_TIMEOUT_MS = 12000`; the single-shot timer starts with the worker and
  is stopped by `_on_status_ready`.
- If it fires first (`_on_status_timeout`), the pill falls back to the locally
  knowable state: `"authenticated"` if a session is already cached, otherwise
  `_credential_state()` ("stored" if credentials/key exist on disk, else "none").
  The worker is still allowed to finish and clean itself up in the background.

## 5. Interactive OAuth flow (personal mode)

**What it does.** When a personal-mode user clicks the primary button and no
session exists, `AuthWorker` runs the GEE localhost OAuth flow: it opens the
browser, waits for the user to grant access, and writes the token — all
cancellable and time-bounded.

**Methodology.**
- `handle_authentication()` first tries to `ee.Initialize` with existing
  credentials; only on `ee.EEException` does it run the browser flow
  (`_run_local_auth_flow`) and re-initialize.
- `_run_local_auth_flow` drives `ee.oauth.Flow("localhost", oauth.SCOPES)`
  manually instead of using the SDK's blocking helper, so it can:
  - open the browser and emit `browser_opened(auth_url)` → the view shows a
    "Waiting for sign-in…" line with a **"Reopen the sign-in page"** link;
  - poll the local callback server with a **1-second** socket timeout in a loop,
    checking `should_cancel()` and a `time.monotonic()` deadline each pass;
  - raise `AuthCancelled` if the user cancels, `AuthTimeout` past the deadline
    (default **180 s**), and always `server_close()` in `finally`.
- After capturing the auth code it calls `oauth._obtain_and_write_token(...)`,
  then `ee.Initialize` + a `listAssets` probe confirms the session is live.

## 6. Service-account flow

**What it does.** In service mode there is no browser. Picking a key file and
clicking the button initializes Earth Engine directly from the JSON key.

**Methodology.**
- `handle_browse_key` opens a file dialog, validates the file via
  `read_service_account_key` (must parse as JSON and contain `client_email`,
  else `ValueError` → warning), saves the path, and **pre-fills** the editable
  Project ID from the key's `project_id` field (`extract_project_id_from_key`,
  best-effort).
- `handle_authentication` in service mode refuses to start without a saved key
  path that still exists on disk.
- `AuthWorker` detects the SA path and calls `authenticate_service_account`,
  which builds `ee.ServiceAccountCredentials(client_email, key_file=path)`,
  `ee.Initialize`s, and probes `listAssets`. This path is synchronous (no
  browser); the worker exists only to keep it off the UI thread.

## 7. Busy / cancel UI states

**What it does.** While a sign-in is in flight the page locks down editable
controls and turns the primary button into a Cancel control; the status pill and
a non-blocking status line communicate progress.

**Methodology.**
- `set_auth_busy(True)` disables the Project ID field, reset/browse/folder
  buttons, the mode toggle, and the status badge; the primary button text
  becomes "Cancel" and the status line reads "Starting authentication…".
- Clicking the button again while `AuthWorker.isRunning()` calls `worker.cancel()`
  (flips the `_is_cancelled` flag the OAuth poll loop checks) and shows
  "Cancelling…".
- `_on_auth_finished(success, message)` clears the busy state, tears down the
  worker (`deleteLater`), and on success sets the authenticated pill, navigates
  to the next page (`show_optical_page`), and pops "Authentication successful!".
  A `CANCELLED` sentinel is swallowed silently; any other message is shown as a
  warning.

## 8. Status pill states & button text

**What it does.** A single status badge communicates sign-in state via color and
text; the primary button's label adapts to that state.

**Methodology.**
- `_AUTH_STATE_STYLES` maps five states to (text, fg, bg, border): `checking`
  (grey), `none` ("Not signed in", red), `stored` ("Credentials found — validate
  to finish", amber), `authenticated` ("Signed in & ready", green),
  `authenticated_sa` ("Signed in via service account", green). Unknown states
  fall back to `stored`.
- When not busy, an `authenticated*` state relabels the primary button to
  "Continue" (so it navigates forward instead of re-signing-in); other states
  reset it to "🔑 Validate ID".
- Editing the Project ID after sign-in (`on_project_id_changed`) invalidates the
  cached session so the user must re-validate against the new project.

## 9. Reset

**What it does.** "Reset authentication" clears the plugin's Earth Engine
configuration so the next sign-in starts clean.

**Methodology.**
- `reset_authentication` raises `FileNotFoundError` if there is nothing to clear
  (no OAuth file and no saved SA path).
- It deletes the OAuth credentials file (if present), forgets the saved SA key
  **path** (the key file on disk is never touched), then reloads `ee.oauth` and
  calls `ee.Reset()` to drop any in-process EE state. Finally it clears the
  cached `is_authenticated` flag.
- The controller clears the SA key input field and re-runs `refresh_auth_status`
  in a `finally`, so the pill reflects the post-reset state regardless of errors.

---

## Performance notes

- **Off-thread checks** — even the "silent" status probe makes a network call,
  so it runs in `AuthStatusWorker`; the UI never blocks on a slow Earth Engine
  round-trip.
- **High-volume endpoint** — every `ee.Initialize` (silent check, OAuth, service
  account) targets `earthengine-highvolume.googleapis.com`, so the session is
  ready for the parallel request fan-out the other pages perform.
- **Bounded waits** — the OAuth flow uses a 180 s deadline with a 1 s polling
  socket timeout, and the status check is capped by a 12 s `QTimer`, so neither a
  slow network nor an abandoned browser tab can wedge the page.
- **Silent re-auth on startup** — a returning user with valid stored credentials
  is signed in automatically without any click.
