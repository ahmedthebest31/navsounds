from __future__ import annotations
from typing import Any, Callable, Optional
from browseMode import BrowseModeTreeInterceptor
from inputCore import InputGesture
import textInfos

class BrowseModeQuickNavInterceptor:
    def __init__(self, plugin_instance):
        self.plugin = plugin_instance
        self.orig_quick_nav_script: Optional[Callable[..., Any]] = None
        self._patched_script_ref: Optional[Callable[..., Any]] = None

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

    def terminate(self) -> None:
        if self.orig_quick_nav_script and self._patched_script_ref:
            current_script = getattr(BrowseModeTreeInterceptor, "_quickNavScript", None)
            if current_script == self._patched_script_ref:
                setattr(BrowseModeTreeInterceptor, "_quickNavScript", self.orig_quick_nav_script)