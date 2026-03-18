from pathlib import Path
from random import choice
from typing import Any, Callable

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
from .browser import BrowseModeQuickNav
from .settings import NavSettingsPanel


addonHandler.initTranslation()
_: Callable[[str], str]


ROLE_SECTION = "NavigationSounds"
confspec = {
    "sayRoles": "boolean(default=false)",
    "sayStates": "boolean(default=true)",
    "soundType": "string(default=default)",
    "cfgSounds": "boolean(default=true)",
    "typing": "boolean(default=true)",
    "type": "string(default=1blueSwitch)",
    "edit": "boolean(default=false)",
    "browser": "boolean(default=true)",
    "browsertype": "string(default=3d)",
    "volume": "integer(default=50)"
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

        NavSettingsPanel.main_plugin = self
        if NavSettingsPanel not in NVDASettingsDialog.categoryClasses:
            NVDASettingsDialog.categoryClasses.append(NavSettingsPanel)

        self.browser = BrowseModeQuickNav(self.play_browser)
        if self.role_section["browser"]:
            self.browser.patch()

        self.old = speech.speech.getPropertiesSpeech
        self.audio_manager = MultiPlayerManager(self.role_section["volume"])
        self.cache_sounds()

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

    @property
    def loc_browser_sounds(self) -> Path:
        browser_type = self.role_section["browsertype"]
        if not browser_type:
            raise ValueError("saved settings sounds type for browser quick nav not found")
        return Path(self.main_paths / "effects" / "browsersounds" / browser_type)

    def cache_sounds(self) -> None:
        for sound_dir in (self.loc_nav_sounds, self.loc_type_sounds, self.loc_browser_sounds,):
            if not sound_dir.is_dir():
                continue

            if sound_dir.parent.name == "navsounds":
                prefix = "nav"
            elif sound_dir.parent.name == "browsersounds":
                prefix = "browser"
            elif sound_dir.parent.name == "typingsound":
                prefix = "type"
            else:
                raise ValueError("Sound type folder not found")

            sound_files = list(sound_dir.glob("*.wav"))
            for sound_file in sound_files:
                name = f"{prefix}_{sound_file.stem.lower()}"
                self.audio_manager.preload_sound(name, sound_file)

        self.nav_sounds = {k for k in self.audio_manager.cache if k.startswith("nav")}
        self.browser_sounds = {k for k in self.audio_manager.cache if k.startswith("browser")}
        self.type_sounds = {k for k in self.audio_manager.cache if k.startswith("type")}
        self.type_sounds_list = list(self.type_sounds)

    def reload_audio(self) -> None:
        self.audio_manager.clear_all()
        self.cache_sounds()

    def play_nav(self, sound_id: str) -> None:
        if not self.cfg_sounds:
            return

        self.audio_manager.play(sound_id)

    def play_typing(self, _: str) -> None:
        if not self.role_section["typing"]:
            return

        if self.type_sounds:
            sound_id = choice(self.type_sounds_list)
            self.audio_manager.play(sound_id)

    def play_browser(self, sound_id: str) -> None:
        if not self.role_section["browser"]:
            return

        self.audio_manager.play(sound_id)

    def _check_and_play_nav(self, name: str) -> bool:
        cache_key = f"nav_{name}"
        if cache_key in self.nav_sounds:
            self.play_nav(cache_key)
            return True
        return False

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
        speech.speech.getPropertiesSpeech = self.old if self.say_states or self.say_roles else self.get_property2_speech

        if self.cfg_sounds:
            played = False
            if obj.states:
                for state in obj.states:
                    name = State(state).name.replace("_", "").lower()
                    played = self._check_and_play_nav(name)
                    if played:
                        break

            if not played:
                name = Role(obj.role).name.replace("_", "").lower()
                self._check_and_play_nav(name)

        nextHandler()

    def get_property2_speech(
            self,
            reason: NVDAObjects.controlTypes.OutputReason = OutputReason.QUERY,
            **kwargs: Any,
    ) -> list[SpeechCommand | str]:
        role = kwargs.get("role", None)
        states = kwargs.get("states", None)

        if role is not None and not self.say_roles:
            if "nav_" + Role(role).name.replace("_", "").lower() in self.nav_sounds:
                del kwargs["role"]

        if states and not self.say_states:
            to_remove = {
                state for state in states
                if "nav_" + State(state).name.replace("_", "").lower() in self.nav_sounds
            }

            for state in to_remove:
                kwargs["states"].discard(state)

        return self.old(reason, **kwargs)

    @script(gesture="kb:NVDA+alt+n")
    def script_toggle(self, unused_gesture: inputCore.InputGesture) -> None:
        cfg_typing = self.role_section["typing"]
        is_same_script = getLastScriptRepeatCount()

        if is_same_script == 0:
            self.cfg_sounds = not self.cfg_sounds
            if self.cfg_sounds is False:
                ui.message(_("Disable navigation sounds"))
            else:
                ui.message(_("Enable navigation sounds"))

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
        speech.speech.getPropertiesSpeech = self.old
        self.browser.terminate()
        self.audio_manager.clear_all()

        try:
            NVDASettingsDialog.categoryClasses.remove(NavSettingsPanel)
        except ValueError:
            pass

        super().terminate()
