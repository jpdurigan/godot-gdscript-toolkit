"""
Utilities for obtaining the gdtoolkit package version without using
deprecated pkg_resources. Falls back gracefully when metadata is
unavailable (e.g., running from source without installation).
"""

import importlib


def get_gdtoolkit_version(default: str = "0") -> str:
    """Return the installed gdtoolkit version or a default fallback.

    Tries stdlib importlib.metadata (Py3.8+) and then the
    importlib-metadata backport. On any lookup failure, returns
    the provided default.
    """

    try:
        metadata = importlib.import_module("importlib.metadata")
    except ModuleNotFoundError:
        try:
            metadata = importlib.import_module("importlib_metadata")
        except ModuleNotFoundError:
            return default

    try:
        return metadata.version("gdtoolkit")  # type: ignore[attr-defined]
    except Exception:  # pylint: disable=broad-except
        return default
