from __future__ import annotations

from typing import Any, Optional

import textInfos
try:
    from logHandler import log
except ImportError:
    log = None

try:
    import vision
except ImportError:
    vision = None


class BrowseModeMoveListener:
    def __init__(self, plugin_instance: Any) -> None:
        self.plugin = plugin_instance
        self._extension_point: Optional[Any] = None
        self._registered = False
        self._logged_errors: set[str] = set()

    def start(self) -> None:
        extension_point = self._get_extension_point()
        if extension_point is None:
            return
        if self._registered and self._extension_point is extension_point:
            return
        if self._registered:
            self.stop()
        extension_point.register(self._on_browse_mode_move)
        self._extension_point = extension_point
        self._registered = True

    def stop(self) -> None:
        if not self._registered or self._extension_point is None:
            self._registered = False
            self._extension_point = None
            return
        try:
            self._extension_point.unregister(self._on_browse_mode_move)
        except Exception:
            self._log_exception_once("unregister", "Failed to unregister browse-mode move listener")
        self._registered = False
        self._extension_point = None

    patch = start
    terminate = stop

    def _get_extension_point(self) -> Optional[Any]:
        handler = getattr(vision, "handler", None)
        extension_points = getattr(handler, "extensionPoints", None)
        return getattr(extension_points, "post_browseModeMove", None)

    def _on_browse_mode_move(self, *args: Any, **kwargs: Any) -> None:
        if not getattr(self.plugin, "cfg_sounds", False):
            return

        cursor_manager = kwargs.get("obj")
        if cursor_manager is None and args:
            cursor_manager = args[0]

        try:
            nav_obj = self._get_object_at_caret(cursor_manager)
            if nav_obj is None:
                return
            self.plugin._play_nav_for_object(nav_obj)
        except Exception:
            self._log_exception_once("dispatch", "Browse-mode navigation sound dispatch failed")

    def _get_object_at_caret(self, cursor_manager: Any) -> Any:
        if hasattr(cursor_manager, "makeTextInfo"):
            try:
                info = cursor_manager.makeTextInfo(textInfos.POSITION_CARET)
            except Exception:
                info = None
            if info is not None:
                for attr in ("NVDAObjectAtStart", "focusableNVDAObjectAtStart"):
                    try:
                        nav_obj = getattr(info, attr)
                    except Exception:
                        nav_obj = None
                    if nav_obj is not None:
                        return nav_obj

        try:
            return cursor_manager.currentNVDAObject
        except Exception:
            return None

    def _log_exception_once(self, key: str, message: str) -> None:
        if key in self._logged_errors:
            return
        self._logged_errors.add(key)
        if log is not None and hasattr(log, "exception"):
            log.exception(message)
