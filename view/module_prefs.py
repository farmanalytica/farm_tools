# -*- coding: utf-8 -*-
"""
User preferences for module ordering and visibility.

Both the sidebar rail and the welcome hub read this module so the two surfaces
stay in sync: reorder or hide a module once and it changes everywhere.

Auth is special — it is always shown and never reordered (pinned first on the
rail, pinned last on the hub) — so it is NOT part of the manageable set here.
"""

from qgis.core import QgsSettings

# Build flavor: a single-module plugin build (e.g. the standalone RAVI / EasyDEM
# / ClimaPlots packages) ships a generated ``_build_flavor.py`` naming the one
# module it defaults to. The full FARM tools build ships no such file, so FLAVOR
# is None and every module shows by default. See build_plugin.py.
try:
    from .._build_flavor import FLAVOR as _FLAVOR
except Exception:
    _FLAVOR = None

# Display label per flavor — used for the QGIS Plugins-menu entry so each
# single-module plugin gets its own submenu instead of all piling under one
# "FARM tools" group. The full build (no flavor) keeps "FARM tools".
_FLAVOR_LABELS = {
    "optical": "RAVI",
    "landsat": "Multi-Satellite",
    "sysi": "SYSI",
    "radar": "AGLgis",
    "download": "EasyDEM",
    "climaplots": "ClimaPlots",
    "fieldguide": "Field Guide",
    "mapbiomas": "MapBiomas",
    "mzones": "Management Zones",
}


def flavor_label(default="FARM tools"):
    """Human label for this build's flavor (the plugin's menu/title name)."""
    return _FLAVOR_LABELS.get(_FLAVOR, default)

# Namespace settings per flavor so two FARM-derived plugins installed side by
# side do not fight over the same order/hidden keys.
_PREFIX = "qgis-RAVI/" + (_FLAVOR + "/" if _FLAVOR else "") + "modules/"
_KEY_ORDER = _PREFIX + "order"
_KEY_HIDDEN = _PREFIX + "hidden"

# Canonical default order of the reorderable / hideable modules (auth excluded —
# it is pinned). Forward-compatible: a module added in a future version that is
# absent from stored prefs is appended here and shown by default, while stored
# keys no longer in this list are dropped.
DEFAULT_ORDER = [
    "optical",
    "landsat",
    "sysi",
    "radar",
    "download",
    "climaplots",
    "fieldguide",
    "mapbiomas",
    "mzones",
]


def _read_list(key):
    """Read a key as a list of str, tolerating QSettings' single-value quirk."""
    raw = QgsSettings().value(key, [])
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, (list, tuple)):
        return [str(x) for x in raw]
    return []


def get_order():
    """Return the manageable module keys in user order.

    Stored order is reconciled with ``DEFAULT_ORDER``: unknown keys are dropped
    and any default key missing from storage is appended, so the result always
    matches exactly the current module set.
    """
    stored = _read_list(_KEY_ORDER)
    order = [k for k in stored if k in DEFAULT_ORDER]
    order += [k for k in DEFAULT_ORDER if k not in order]
    return order


def _default_hidden():
    """Default hidden set before the user customizes anything.

    Full build: nothing hidden. Single-module flavor build: every module except
    the flavor's own is hidden, so the plugin opens showing just its module
    (the rest remain discoverable via the welcome hub's "More tools" strip)."""
    if _FLAVOR and _FLAVOR in DEFAULT_ORDER:
        return {k for k in DEFAULT_ORDER if k != _FLAVOR}
    return set()


def get_hidden():
    """Return the set of hidden manageable module keys.

    If the user has never customized visibility, fall back to the flavor default
    (see :func:`_default_hidden`); once they customize, their stored set wins —
    even when empty (all shown)."""
    if QgsSettings().value(_KEY_HIDDEN, None) is None:
        return _default_hidden()
    return {k for k in _read_list(_KEY_HIDDEN) if k in DEFAULT_ORDER}


def is_hidden(key):
    return key in get_hidden()


def set_prefs(order, hidden):
    """Persist module ``order`` (list) and ``hidden`` keys (iterable)."""
    settings = QgsSettings()
    settings.setValue(_KEY_ORDER, [k for k in order if k in DEFAULT_ORDER])
    settings.setValue(_KEY_HIDDEN, [k for k in hidden if k in DEFAULT_ORDER])


def unhide(key):
    """Remove ``key`` from the hidden set, keeping order untouched.

    Used by the welcome hub's "More tools" teaser cards so a single click
    activates an included-but-hidden module.
    """
    if key not in DEFAULT_ORDER:
        return
    hidden = get_hidden()
    hidden.discard(key)
    set_prefs(get_order(), hidden)


def reset():
    """Clear stored prefs — back to default order with every module visible."""
    settings = QgsSettings()
    settings.remove(_KEY_ORDER)
    settings.remove(_KEY_HIDDEN)
