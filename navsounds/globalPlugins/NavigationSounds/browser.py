from __future__ import annotations

from typing import Any, Callable, Optional

from browseMode import BrowseModeTreeInterceptor
from inputCore import InputGesture
import textInfos


class BrowseModeQuickNav:

    def __init__(self, play_func: Callable[[str], None]):
        self.play = play_func
        self.orig_quick_nav_script: Optional[Callable[..., Any]] = None

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

            selection: Optional[textInfos.TextInfo] = getattr(instance, "selection", None)
            if not selection:
                make_text_info = getattr(instance, "makeTextInfo", None)
                if not make_text_info:
                    return
                selection = make_text_info(textInfos.POSITION_CARET)
            old_info: textInfos.TextInfo = selection.copy()

            self.orig_quick_nav_script(
                instance,
                gesture,
                itemType,
                direction,
                errorMessage,
                readUnit,
                *args,
                **kwargs
            )

            new_selection: Optional[textInfos.TextInfo] = getattr(instance, "selection", None)
            if not new_selection:
                make_text_info = getattr(instance, "makeTextInfo", None)
                if not make_text_info:
                    return
                new_selection = make_text_info(textInfos.POSITION_CARET)

            if not old_info.compareEndPoints(new_selection, "startToStart") == 0:
                self.play(f"browser_{itemType}")

        setattr(BrowseModeTreeInterceptor, "_quickNavScript", patched_quick_nav_script)

    def terminate(self) -> None:
        if self.orig_quick_nav_script:
            setattr(BrowseModeTreeInterceptor, "_quickNavScript", self.orig_quick_nav_script)
