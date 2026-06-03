from __future__ import annotations
from typing import Any, Callable, Optional
from browseMode import BrowseModeTreeInterceptor
from controlTypes import Role, State
from inputCore import InputGesture
import textInfos
import cursorManager


class BrowseModeQuickNavInterceptor:
    def __init__(self, plugin_instance):
        self.plugin = plugin_instance
        self.orig_quick_nav_script: Optional[Callable[..., Any]] = None
        self._patched_script_ref: Optional[Callable[..., Any]] = None
        self.orig_caret_movement: Optional[Callable[..., Any]] = None
        self._patched_caret_ref: Optional[Callable[..., Any]] = None

    def patch(self) -> None:
        self.orig_quick_nav_script = getattr(BrowseModeTreeInterceptor, "_quickNavScript", None)

        def patched_quick_nav_script(
                instance: BrowseModeTreeInterceptor,
                gesture: Optional[InputGesture],
                itemType: str,
                direction: str,
                errorMessage: str,
                readUnit: Any,
                *args: Any,
                **kwargs: Any
        ) -> None:
            if self.orig_quick_nav_script is None:
                return

            try:
                selection = instance.selection
            except Exception:
                selection = None

            if not selection and hasattr(instance, "makeTextInfo"):
                try:
                    selection = instance.makeTextInfo(textInfos.POSITION_CARET)
                except Exception:
                    pass

            old_info = selection.copy() if selection else None

            self.orig_quick_nav_script(
                instance, gesture, itemType, direction, errorMessage, readUnit, *args, **kwargs
            )

            try:
                new_selection = instance.selection
            except Exception:
                new_selection = None

            if not new_selection and hasattr(instance, "makeTextInfo"):
                try:
                    new_selection = instance.makeTextInfo(textInfos.POSITION_CARET)
                except Exception:
                    pass

            if old_info and new_selection:
                if old_info.compareEndPoints(new_selection, "startToStart") != 0:
                    self.plugin._check_and_play_nav(itemType)

        self._patched_script_ref = patched_quick_nav_script
        setattr(BrowseModeTreeInterceptor, "_quickNavScript", patched_quick_nav_script)

        self.orig_caret_movement = getattr(cursorManager.CursorManager, "_caretMovementScriptHelper", None)

        def patched_caret_movement(
                instance: Any,
                gesture: Any,
                unit: Any,
                *args: Any,
                **kwargs: Any
        ) -> None:
            if self.orig_caret_movement is None:
                return

            try:
                old_info = instance.makeTextInfo(textInfos.POSITION_CARET)
            except Exception:
                old_info = None

            self.orig_caret_movement(instance, gesture, unit, *args, **kwargs)

            if not self.plugin.cfg_sounds:
                return

            try:
                new_info = instance.makeTextInfo(textInfos.POSITION_CARET)
            except Exception:
                return

            if old_info and old_info.compareEndPoints(new_info, "startToStart") == 0:
                return

            obj = self._get_object_at_caret(instance)
            if obj is None:
                return

            played = False
            if obj.states:
                for state in obj.states:
                    name = State(state).name.replace("_", "").lower()
                    if self.plugin._check_and_play_nav(name):
                        played = True
                        break

            if not played:
                name = Role(obj.role).name.replace("_", "").lower()
                self.plugin._check_and_play_nav(name)

        self._patched_caret_ref = patched_caret_movement
        setattr(cursorManager.CursorManager, "_caretMovementScriptHelper", patched_caret_movement)

    def _get_object_at_caret(self, instance: Any) -> Any:
        if hasattr(instance, "currentNVDAObject"):
            try:
                return instance.currentNVDAObject
            except Exception:
                pass

        if hasattr(instance, "makeTextInfo"):
            try:
                info = instance.makeTextInfo(textInfos.POSITION_CARET)
                return info.focusableNVDAObjectAtStart
            except Exception:
                pass

        return None

    def terminate(self) -> None:
        if self.orig_quick_nav_script and self._patched_script_ref:
            current_script = getattr(BrowseModeTreeInterceptor, "_quickNavScript", None)
            if current_script == self._patched_script_ref:
                setattr(BrowseModeTreeInterceptor, "_quickNavScript", self.orig_quick_nav_script)

        if self.orig_caret_movement and self._patched_caret_ref:
            current_caret = getattr(cursorManager.CursorManager, "_caretMovementScriptHelper", None)
            if current_caret == self._patched_caret_ref:
                setattr(cursorManager.CursorManager, "_caretMovementScriptHelper", self.orig_caret_movement)
