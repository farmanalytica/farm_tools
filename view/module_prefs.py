# -*- coding: utf-8 -*-
"""
User preferences for module ordering and visibility.

Both the sidebar rail and the welcome hub read this module so the two surfaces
stay in sync: reorder or hide a module once and it changes everywhere.

Auth is special — it is always shown and never reordered (pinned first on the
rail, pinned last on the hub) — so it is NOT part of the manageable set here.
"""

from qgis.core import QgsSettings

_PREFIX = "qgis-RAVI/modules/"
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


def get_hidden():
    """Return the set of hidden manageable module keys."""
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
