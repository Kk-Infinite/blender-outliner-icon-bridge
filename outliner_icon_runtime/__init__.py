"""Copy this directory into a Blender add-on and import its public API."""

import os

from .bridge import HookDiagnostics, NATIVE_API_VERSION, OutlinerIconBridge


RUNTIME_DIRECTORY = os.path.dirname(__file__)
BUNDLED_ASSET_DIRECTORY = os.path.join(RUNTIME_DIRECTORY, "assets", "icons")


def bundled_asset_path(filename: str) -> str:
    """Return the absolute path of an icon shipped with this runtime package."""
    return os.path.join(BUNDLED_ASSET_DIRECTORY, filename)


__all__ = (
    "BUNDLED_ASSET_DIRECTORY",
    "HookDiagnostics",
    "NATIVE_API_VERSION",
    "OutlinerIconBridge",
    "RUNTIME_DIRECTORY",
    "bundled_asset_path",
)
