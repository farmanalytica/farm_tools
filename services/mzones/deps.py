# -*- coding: utf-8 -*-
"""Optional dependency helpers.

Third-party libs (pandas, scikit-learn, scipy) are shipped via extlibs.zip and
may be absent until downloaded. Services call these helpers and raise
`DependencyMissing` on absence; controllers catch it and show the standard
bilingual "install instructions" message.
"""
from .i18n import tr


class DependencyMissing(Exception):
    """Raised when an optional Python package is not importable."""

    def __init__(self, package: str):
        self.package = package
        super().__init__(package)

    def user_message(self) -> str:
        return tr("This feature requires the Python package '{}'.\nOpen the Management Zones intro tab and click 'Install dependencies'.").format(self.package)


def import_pandas():
    try:
        import pandas as pd
        return pd
    except Exception:
        raise DependencyMissing("pandas")


def try_pandas():
    """Return the pandas module or None (for soft checks)."""
    try:
        import pandas as pd
        return pd
    except Exception:
        return None


# (display name, import module) for the Python deps shipped via extlibs.
PY_DEPS = (("pandas", "pandas"), ("scikit-learn", "sklearn"), ("scipy", "scipy"))


def check_imports() -> dict:
    """Return {display_name: importable_bool} for the bundled Python deps."""
    res = {}
    for name, mod in PY_DEPS:
        try:
            __import__(mod)
            res[name] = True
        except Exception:
            res[name] = False
    return res
