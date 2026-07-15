"""Standalone Python integration layer for the Outliner icon hook.

This module owns only the mappings it creates.  It can be vendored as a
submodule of another Blender add-on; no native rebuild is needed.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

import bpy
import bpy.utils.previews

__all__ = ("HookDiagnostics", "NATIVE_API_VERSION", "OutlinerIconBridge")

NATIVE_API_VERSION = 2
DEFAULT_DLL_RELATIVE_PATH = os.path.join(
    "native", "bin", "Release", "outliner_icon_hook_v3.dll"
)
DEFAULT_KNOWN_BUILDS_RELATIVE_PATH = "known_builds.json"


@dataclass(frozen=True)
class HookDiagnostics:
    ready: bool
    error: str
    mappings: int
    calls: int
    overrides: int


class OutlinerIconBridge:
    """Registers preview images and binds their dynamic IDs to Blender objects.

    A bridge instance is intentionally independent from any example add-on.
    Consumers retain ownership of asset metadata and must call ``clear`` before
    deleting an object, then call ``rebind`` after loading a .blend file.
    """

    def __init__(
        self,
        addon_directory: str | None = None,
        dll_path: str | None = None,
        known_builds_path: str | None = None,
    ):
        self._addon_directory = os.path.abspath(addon_directory or os.path.dirname(__file__))
        self._dll_path = os.path.abspath(
            dll_path or os.path.join(self._addon_directory, DEFAULT_DLL_RELATIVE_PATH)
        )
        self._known_builds_path = os.path.abspath(
            known_builds_path
            or os.path.join(self._addon_directory, DEFAULT_KNOWN_BUILDS_RELATIVE_PATH)
        )
        self._assets: Dict[str, str] = {}
        self._owned_pointers: set[int] = set()
        self._previews = None
        self._native_hook = None
        self._ready = False
        self._error = "not initialized"

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def error(self) -> str:
        return self._error

    def install(self) -> bool:
        if self._native_hook is not None:
            if self._ready:
                return True
            return self._install_native_hook()
        if not os.path.isfile(self._dll_path):
            self._error = "native DLL file not found: " + self._dll_path
            return False
        try:
            native_hook = ctypes.CDLL(self._dll_path)
            native_hook.outliner_icon_hook_install.restype = ctypes.c_int
            native_hook.outliner_icon_hook_install_at_rva.argtypes = (ctypes.c_uint,)
            native_hook.outliner_icon_hook_install_at_rva.restype = ctypes.c_int
            native_hook.outliner_icon_hook_set.argtypes = (ctypes.c_void_p, ctypes.c_int)
            native_hook.outliner_icon_hook_clear.argtypes = (ctypes.c_void_p,)
            native_hook.outliner_icon_hook_call_count.restype = ctypes.c_ulonglong
            native_hook.outliner_icon_hook_override_count.restype = ctypes.c_ulonglong
            native_hook.outliner_icon_hook_mapping_count.restype = ctypes.c_uint
            self._native_hook = native_hook
            return self._install_native_hook()
        except OSError as error:
            self._native_hook = None
            self._ready = False
            self._error = str(error)
        return self._ready

    def _install_native_hook(self) -> bool:
        known_build = self._find_known_build()
        if known_build is not None:
            self._ready = bool(
                self._native_hook.outliner_icon_hook_install_at_rva(known_build["rva"])
            )
            build_name = known_build["name"]
            self._error = (
                "ready (known build: " + build_name + ")"
                if self._ready
                else "known build hook install failed: " + build_name
            )
            return self._ready

        self._ready = bool(self._native_hook.outliner_icon_hook_install())
        self._error = "ready (PDB/DIA)" if self._ready else "known build not found; PDB/DIA hook install failed"
        return self._ready

    def _find_known_build(self):
        if not os.path.isfile(self._known_builds_path):
            return None
        executable_path = bpy.app.binary_path
        if not executable_path or not os.path.isfile(executable_path):
            return None
        try:
            with open(executable_path, "rb") as executable_file:
                digest = hashlib.sha256()
                while chunk := executable_file.read(1024 * 1024):
                    digest.update(chunk)
                executable_hash = digest.hexdigest()
            with open(self._known_builds_path, "r", encoding="utf-8") as known_builds_file:
                known_builds = json.load(known_builds_file)
            for build in known_builds.get("builds", ()):
                if build.get("blender_exe_sha256", "").lower() == executable_hash:
                    return {
                        "name": build["name"],
                        "rva": int(build["outliner_icon_rva"], 0),
                    }
        except (KeyError, OSError, ValueError, json.JSONDecodeError):
            return None
        return None

    def register_asset(self, key: str, image_path: str) -> None:
        if not isinstance(key, str) or not key:
            raise ValueError("asset key must be a non-empty string")
        normalized_path = os.path.abspath(image_path)
        if not os.path.isfile(normalized_path):
            raise FileNotFoundError(normalized_path)
        previous_path = self._assets.get(key)
        if previous_path is not None and previous_path != normalized_path:
            raise ValueError("asset key is already registered with another path: " + key)
        if previous_path is None and self._previews is not None:
            raise RuntimeError("register all assets before the first bind")
        self._assets[key] = normalized_path

    def bind(self, obj: bpy.types.Object, asset_key: str) -> bool:
        if asset_key not in self._assets:
            raise KeyError("unknown icon asset: " + asset_key)
        if not self.install():
            return False
        previews = self._load_previews()
        icon_id = previews[asset_key].icon_id
        if icon_id <= 0:
            self._error = "Blender did not assign a UI preview icon ID"
            return False
        object_pointer = obj.as_pointer()
        self._native_hook.outliner_icon_hook_set(ctypes.c_void_p(object_pointer), icon_id)
        self._owned_pointers.add(object_pointer)
        return True

    def clear(self, obj: bpy.types.Object) -> None:
        self.clear_pointer(obj.as_pointer())

    def clear_pointer(self, object_pointer: int) -> None:
        if self._native_hook is not None:
            self._native_hook.outliner_icon_hook_clear(ctypes.c_void_p(object_pointer))
        self._owned_pointers.discard(object_pointer)

    def clear_owned(self) -> None:
        for object_pointer in tuple(self._owned_pointers):
            self.clear_pointer(object_pointer)

    def rebind(self, bindings: Iterable[Tuple[bpy.types.Object, str]]) -> int:
        self.clear_owned()
        bound = 0
        for obj, asset_key in bindings:
            bound += int(self.bind(obj, asset_key))
        self.redraw_outliners()
        return bound

    def diagnostics(self) -> HookDiagnostics:
        if self._native_hook is None:
            return HookDiagnostics(self._ready, self._error, 0, 0, 0)
        return HookDiagnostics(
            self._ready,
            self._error,
            self._native_hook.outliner_icon_hook_mapping_count(),
            self._native_hook.outliner_icon_hook_call_count(),
            self._native_hook.outliner_icon_hook_override_count(),
        )

    def close(self) -> None:
        self.clear_owned()
        if self._previews is not None:
            bpy.utils.previews.remove(self._previews)
            self._previews = None

    def redraw_outliners(self) -> None:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'OUTLINER':
                    area.tag_redraw()

    def _load_previews(self):
        if self._previews is None:
            self._previews = bpy.utils.previews.new()
            for key, image_path in self._assets.items():
                self._previews.load(key, image_path, 'IMAGE', force_reload=True)
        return self._previews
