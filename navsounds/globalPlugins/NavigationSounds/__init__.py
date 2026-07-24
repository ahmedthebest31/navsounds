import time
from pathlib import Path
from random import choice
from typing import Any, Callable

import wx

import addonHandler
import config
from controlTypes import OutputReason, Role, State
import globalPluginHandler
from gui.settingsDialogs import NVDASettingsDialog
import inputCore
import NVDAObjects
from scriptHandler import script, getLastScriptRepeatCount
import speech
from speech.commands import SpeechCommand
import ui

from .audio import MultiPlayerManager
from .settings import NavSettingsPanel
from .browser import BrowseModeMoveListener

addonHandler.initTranslation()
_: Callable[[str], str]

ROLE_SECTION = "NavigationSounds"
confspec = {
    "sayRoles": "boolean(default=false)",
    "sayStates": "boolean(default=true)",
    "soundType": "string(default=default)",
    "cfgSounds": "boolean(default=true)",
    "mouseSounds": "boolean(default=false)",
    "mouseHoverDelay": "integer(default=270)",
    "typing": "boolean(default=true)",
    "type": "string(default=1blueSwitch)",
    "edit": "boolean(default=false)",
    "volume": "integer(default=50)",
    "arrowNavSounds": "boolean(default=true)"
}

if config.conf is not None:
    config.conf.spec[ROLE_SECTION] = confspec

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    scriptCategory = _("navigation sounds")

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        self.cfg_sounds = self.role_section["cfgSounds"]
        self.say_roles = self.role_section["sayRoles"]
        self.say_states = self.role_section["sayStates"]

        self._last_type_time = 0.0
        self._last_nav_time = 0.0
        self._last_nav_obj = None
        self._last_mouse_time = 0.0
        self._last_mouse_obj = None
        self._mouse_timer = None

        NavSettingsPanel.main_plugin = self
        if NavSettingsPanel not in NVDASettingsDialog.categoryClasses:
            NVDASettingsDialog.categoryClasses.append(NavSettingsPanel)

        try:
            self._speech_module, self._speech_attr, self.old_getPropertiesSpeech = (
                self._get_properties_speech_target()
            )
            setattr(self._speech_module, self._speech_attr, self.get_property2_speech)
        except Exception:
            self.old_getPropertiesSpeech = getattr(speech.speech, "getPropertiesSpeech", None)
            if self.old_getPropertiesSpeech is not None:
                speech.speech.getPropertiesSpeech = self.get_property2_speech

        self.audio_manager = MultiPlayerManager(self.role_section["volume"])
        self.cache_sounds()

        self.browser_interceptor = BrowseModeMoveListener(self)
        if self.cfg_sounds:
            self.browser_interceptor.patch()

    @property
    def role_section(self) -> dict[str, Any]:
        if config.conf is None or not config.conf.get(ROLE_SECTION):
            raise ValueError("saved settings section not found")
        return config.conf.get(ROLE_SECTION)

    @property
    def main_paths(self) -> Path:
        return Path(__file__).resolve().parent

    @property
    def loc_nav_sounds(self) -> Path:
        nav_type = self.role_section.get("soundType")
        if not nav_type:
            raise ValueError("saved settings sound type for navigation not found")
        return Path(self.main_paths / "effects" / "navsounds" / nav_type)

    @property
    def loc_type_sounds(self) -> Path:
        typing_type = self.role_section["type"]
        if not typing_type:
            raise ValueError("saved settings sound type for typing not found")
        return Path(self.main_paths / "effects" / "typingsound" / typing_type)

    def cache_sounds(self) -> None:
        for sound_dir in (self.loc_nav_sounds, self.loc_type_sounds,):
            if not sound_dir.is_dir():
                continue

            if sound_dir.parent.name == "navsounds":
                prefix = "nav"
            elif sound_dir.parent.name == "typingsound":
                prefix = "type"
            else:
                raise ValueError("Sound type folder not found")

            sound_files = list(sound_dir.glob("*.wav"))
            for sound_file in sound_files:
                name = f"{prefix}_{sound_file.stem.lower()}"
                self.audio_manager.preload_sound(name, sound_file)

        self.nav_sounds = {k for k in self.audio_manager.cache if k.startswith("nav")}
        self.type_sounds = {k for k in self.audio_manager.cache if k.startswith("type")}
        self.type_sounds_list = list(self.type_sounds)

    def reload_audio(self) -> None:
        self.audio_manager.clear_all()
        self.cache_sounds()

    def play_nav(self, sound_id: str) -> None:
        if not self.cfg_sounds:
            return

        now = time.time()
        if now - self._last_nav_time < 0.06:
            return
        self._last_nav_time = now

        self.audio_manager.play(sound_id)

    def play_typing(self, _: str) -> None:
        if not self.role_section["typing"]:
            return

        now = time.time()
        if now - self._last_type_time < 0.07:
            return
        self._last_type_time = now

        if self.type_sounds:
            sound_id = choice(self.type_sounds_list)
            self.audio_manager.play(sound_id)

    def _check_and_play_nav(self, name: str) -> bool:
        cache_key = f"nav_{name}"
        if cache_key in self.nav_sounds:
            self.play_nav(cache_key)
            return True
        return False

    @staticmethod
    def _get_properties_speech_target() -> tuple[Any, str, Callable[..., list[SpeechCommand | str]]]:
        get_properties_speech = getattr(speech, "getPropertiesSpeech", None)
        if get_properties_speech is not None:
            return speech, "getPropertiesSpeech", get_properties_speech

        legacy_speech_module = getattr(speech, "speech", None)
        get_properties_speech = getattr(legacy_speech_module, "getPropertiesSpeech", None)
        if get_properties_speech is not None:
            return legacy_speech_module, "getPropertiesSpeech", get_properties_speech

        raise AttributeError("speech.getPropertiesSpeech is not available")

    def _play_nav_for_object(self, obj: NVDAObjects.NVDAObject) -> bool:
        if not self.cfg_sounds or obj is None:
            return False

        now = time.time()
        obj_id = (
            getattr(obj, "windowHandle", None),
            getattr(obj, "windowControlID", None),
        )
        if obj_id == self._last_nav_obj and (now - self._last_nav_time) < 0.15:
            return False
        self._last_nav_obj = obj_id

        states = getattr(obj, "states", None)
        if states:
            for state in states:
                try:
                    name = State(state).name.replace("_", "").lower()
                except ValueError:
                    continue
                if self._check_and_play_nav(name):
                    return True

        role = getattr(obj, "role", None)
        if role is None:
            return False

        try:
            name = Role(role).name.replace("_", "").lower()
        except ValueError:
            return False
        return self._check_and_play_nav(name)

    def editable(self, obj: NVDAObjects.NVDAObject) -> bool:
        controls = (8, 52, 82,)
        return (obj.role in controls or State.EDITABLE in obj.states) and State.READONLY not in obj.states

    def event_typedCharacter(self, obj: NVDAObjects.NVDAObject, nextHandler: Callable[[], None], ch: str) -> None:
        if self.role_section["edit"]:
            if self.editable(obj):
                self.play_typing(ch)
        else:
            self.play_typing(ch)
        nextHandler()

    def event_gainFocus(self, obj: NVDAObjects.NVDAObject, nextHandler: Callable[[], None]) -> None:
        self._play_nav_for_object(obj)
        nextHandler()

    def _play_mouse_sound_delayed(self, obj: NVDAObjects.NVDAObject) -> None:
        if obj == getattr(self, "_last_mouse_obj", None):
            self._play_nav_for_object(obj)

    def event_mouseMove(self, obj: NVDAObjects.NVDAObject, nextHandler: Callable[[], None], x: int, y: int) -> None:
        if self.role_section.get("mouseSounds", False):
            ignored_roles = {Role.DOCUMENT, Role.WINDOW, Role.PANE, Role.APPLICATION, Role.UNKNOWN}

            if getattr(obj, "role", None) not in ignored_roles and obj != getattr(self, "_last_mouse_obj", None):
                now = time.time()
                delay_ms = self.role_section.get("mouseHoverDelay", 270)
                delay_sec = delay_ms / 1000.0

                if now - getattr(self, "_last_mouse_time", 0.0) < delay_sec:
                    nextHandler()
                    return

                self._last_mouse_time = now
                self._last_mouse_obj = obj

                if getattr(self, "_mouse_timer", None) is not None:
                    self._mouse_timer.Stop()
                    self._mouse_timer = None

                self._mouse_timer = wx.CallLater(delay_ms, self._play_mouse_sound_delayed, obj)

        nextHandler()

    def get_property2_speech(
            self,
            reason: NVDAObjects.controlTypes.OutputReason = OutputReason.QUERY,
            **kwargs: Any,
    ) -> list[SpeechCommand | str]:
        try:
            role = kwargs.get("role", None)
            states = kwargs.get("states", None)

            if role is not None and not self.say_roles:
                try:
                    if "nav_" + Role(role).name.replace("_", "").lower() in self.nav_sounds:
                        if "role" in kwargs:
                            del kwargs["role"]
                except ValueError:
                    pass

            if states and not self.say_states:
                to_remove = set()
                for state in states:
                    try:
                        if "nav_" + State(state).name.replace("_", "").lower() in self.nav_sounds:
                            to_remove.add(state)
                    except ValueError:
                        continue

                if to_remove:
                    if isinstance(states, set):
                        kwargs = {k: (states - to_remove if k == "states" else v) for k, v in kwargs.items()}
                    elif isinstance(states, list):
                        kwargs = {k: ([s for s in states if s not in to_remove] if k == "states" else v) for k, v in kwargs.items()}
        except Exception:
            pass

        if hasattr(self, "old_getPropertiesSpeech") and self.old_getPropertiesSpeech is not None:
            return self.old_getPropertiesSpeech(reason, **kwargs)
        return []

    @script(gesture="kb:NVDA+alt+n")
    def script_toggle(self, unused_gesture: inputCore.InputGesture) -> None:
        cfg_typing = self.role_section["typing"]
        is_same_script = getLastScriptRepeatCount()

        if is_same_script == 0:
            self.cfg_sounds = not self.cfg_sounds
            if self.cfg_sounds is False:
                ui.message(_("Disable navigation sounds"))
                try:
                    self.browser_interceptor.terminate()
                except Exception:
                    pass
            else:
                ui.message(_("Enable navigation sounds"))
                try:
                    self.browser_interceptor.patch()
                except Exception:
                    pass

        elif is_same_script == 1:
            cfg_typing = not cfg_typing
            if cfg_typing is False:
                ui.message(_("Disable typing sounds"))
            else:
                ui.message(_("Enable typing sounds"))

        self.role_section["typing"] = cfg_typing
        self.role_section["cfgSounds"] = self.cfg_sounds

    script_toggle.__doc__ = _(
        "Pressing it once toggles between on and off object sounds, "
        "and Pressing twice  it toggles between on and off typing sounds."
    )

    def terminate(self) -> None:
        if hasattr(self, "_speech_module") and hasattr(self, "_speech_attr") and hasattr(self, "old_getPropertiesSpeech"):
            try:
                setattr(self._speech_module, self._speech_attr, self.old_getPropertiesSpeech)
            except Exception:
                pass
        elif hasattr(self, "old_getPropertiesSpeech") and self.old_getPropertiesSpeech is not None:
            try:
                speech.speech.getPropertiesSpeech = self.old_getPropertiesSpeech
            except Exception:
                pass

        try:
            self.browser_interceptor.terminate()
        except Exception:
            pass

        self.audio_manager.terminate()

        if self._mouse_timer is not None:
            self._mouse_timer.Stop()
            self._mouse_timer = None

        try:
            NVDASettingsDialog.categoryClasses.remove(NavSettingsPanel)
        except ValueError:
            pass

        super().terminate()
