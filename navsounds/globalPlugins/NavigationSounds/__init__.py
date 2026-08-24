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
from logHandler import log
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
# Repeated focus/caret events for the SAME element within this window are
# treated as duplicates and suppressed. Electron/Chromium re-sends focus and
# caret events for one element with 100ms-400ms spacing, so the old 60ms
# time-only throttle let duplicates through.
NAV_DUPLICATE_WINDOW_SECONDS = 0.25
# Fallback throttle when no object identity is available for dedup.
NAV_NO_OBJECT_THROTTLE_SECONDS = 0.06
# Announcement filtering only applies to the reasons that actually play
# navigation sounds. Verified against official NVDA source
# (source/controlTypes/outputReason.py): FOCUS covers focus changes,
# CARET covers caret movement (including browse-mode arrows) and QUICKNAV
# covers quick-navigation announcements. Matched by member NAME so the gate
# survives enum identity differences or plain-string reasons across NVDA
# versions. Every other reason (QUERY, SAYALL, MOUSE, ...) keeps announcing
# roles/states so context is never lost.
_SOUND_REASON_NAMES = frozenset({"FOCUS", "CARET", "QUICKNAV"})


def _reason_plays_nav_sounds(reason: Any) -> bool:
	name = getattr(reason, "name", None)
	if name is None:
		name = str(reason).rsplit(".", maxsplit=1)[-1]
	return name.upper() in _SOUND_REASON_NAMES
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
	"arrowNavSounds": "boolean(default=true)",
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
		self._last_mouse_time = 0.0
		self._last_mouse_obj = None
		self._mouse_timer = None

		NavSettingsPanel.main_plugin = self
		if NavSettingsPanel not in NVDASettingsDialog.categoryClasses:
			NVDASettingsDialog.categoryClasses.append(NavSettingsPanel)

		try:
			self._speech_module, self._speech_attr, self.old_getPropertiesSpeech = self._get_properties_speech_target()
			setattr(self._speech_module, self._speech_attr, self.get_property2_speech)
			# Also patch speech package level for external callers
			self._old_speech_pkg_fn = None
			if self._speech_module is not speech:
				self._old_speech_pkg_fn = getattr(speech, "getPropertiesSpeech", None)
				if self._old_speech_pkg_fn is not None:
					speech.getPropertiesSpeech = self.get_property2_speech
		except Exception:
			self.old_getPropertiesSpeech = getattr(speech.speech, "getPropertiesSpeech", None)
			if self.old_getPropertiesSpeech is not None:
				speech.speech.getPropertiesSpeech = self.get_property2_speech
			self._old_speech_pkg_fn = None

		self.audio_manager = MultiPlayerManager(self.role_section["volume"])
		# Sound sets exist (empty) immediately; the background loader fills them.
		self._refresh_sound_sets()
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

	def _collect_sound_entries(self) -> list[tuple[str, Path]]:
		entries: list[tuple[str, Path]] = []
		for sound_dir, prefix in (
			(self.loc_nav_sounds, "nav"),
			(self.loc_type_sounds, "type"),
		):
			if not sound_dir.is_dir():
				continue
			for sound_file in sorted(sound_dir.glob("*.wav")):
				entries.append((f"{prefix}_{sound_file.stem.lower()}", sound_file))
		return entries

	def _refresh_sound_sets(self) -> None:
		cache = self.audio_manager.cache
		self.nav_sounds = {k for k in cache if k.startswith("nav")}
		self.type_sounds = {k for k in cache if k.startswith("type")}
		self.type_sounds_list = list(self.type_sounds)

	def cache_sounds(self) -> None:
		# Decoding runs on a background thread; sets are refreshed via callback.
		self.audio_manager.load_sounds(self._collect_sound_entries(), on_done=self._refresh_sound_sets)

	def reload_audio(self) -> None:
		self.audio_manager.clear_players()
		self.cache_sounds()

	def play_nav(self, sound_id: str, obj: NVDAObjects.NVDAObject | None = None) -> None:
		if not self.cfg_sounds:
			return

		now = time.monotonic()
		elapsed = now - getattr(self, "_last_nav_time", 0.0)

		if obj is not None:
			last_obj = getattr(self, "_last_nav_obj", None)
			if elapsed < NAV_DUPLICATE_WINDOW_SECONDS and last_obj is not None and obj == last_obj:
				# Duplicate event for the same element (common in Electron/Chromium).
				return
		elif elapsed < NAV_NO_OBJECT_THROTTLE_SECONDS:
			# No element identity available: fall back to a short global throttle.
			return

		self._last_nav_time = now
		self._last_nav_obj = obj
		self.audio_manager.play(sound_id)

	def play_typing(self, _: str) -> None:
		if not self.role_section["typing"]:
			return

		now = time.monotonic()
		if now - self._last_type_time < 0.07:
			return
		self._last_type_time = now

		if self.type_sounds:
			sound_id = choice(self.type_sounds_list)
			self.audio_manager.play(sound_id)

	def _check_and_play_nav(self, name: str, obj: NVDAObjects.NVDAObject | None = None) -> bool:
		cache_key = f"nav_{name}"
		if cache_key in self.nav_sounds:
			self.play_nav(cache_key, obj)
			return True
		return False

	@staticmethod
	def _get_properties_speech_target() -> tuple[Any, str, Callable[..., list[SpeechCommand | str]]]:
		# Priority: speech.speech is where getPropertiesSpeech is defined
		# and where getObjectPropertiesSpeech calls it from (same module).
		# Patching speech.speech ensures the hook is reached by internal callers.
		inner_module = getattr(speech, "speech", None)
		get_properties_speech = getattr(inner_module, "getPropertiesSpeech", None)
		if get_properties_speech is not None:
			return inner_module, "getPropertiesSpeech", get_properties_speech

		get_properties_speech = getattr(speech, "getPropertiesSpeech", None)
		if get_properties_speech is not None:
			return speech, "getPropertiesSpeech", get_properties_speech

		raise AttributeError("speech.getPropertiesSpeech is not available")

	def _play_nav_for_object(self, obj: NVDAObjects.NVDAObject) -> bool:
		if not self.cfg_sounds or obj is None:
			return False

		states = getattr(obj, "states", None)
		if states:
			for state in states:
				try:
					name = State(state).name.replace("_", "").lower()
				except ValueError:
					continue
				if self._check_and_play_nav(name, obj):
					return True

		role = getattr(obj, "role", None)
		if role is None:
			return False

		try:
			name = Role(role).name.replace("_", "").lower()
		except ValueError:
			return False
		return self._check_and_play_nav(name, obj)

	def editable(self, obj: NVDAObjects.NVDAObject) -> bool:
		controls = (
			8,
			52,
			82,
		)
		return (obj.role in controls or State.EDITABLE in obj.states) and State.READONLY not in obj.states

	def event_typedCharacter(self, obj: NVDAObjects.NVDAObject, nextHandler: Callable[[], None], ch: str) -> None:
		if self.role_section["edit"]:
			if self.editable(obj):
				self.play_typing(ch)
		else:
			self.play_typing(ch)
		nextHandler()

	def event_gainFocus(self, obj: NVDAObjects.NVDAObject, nextHandler: Callable[[], None]) -> None:
		# Duplicate focus events for the same element are suppressed centrally
		# inside play_nav (object identity + time window).
		self._play_nav_for_object(obj)
		nextHandler()

	def _play_mouse_sound_delayed(self, obj: NVDAObjects.NVDAObject) -> None:
		if obj == getattr(self, "_last_mouse_obj", None):
			self._play_nav_for_object(obj)

	def event_mouseMove(self, obj: NVDAObjects.NVDAObject, nextHandler: Callable[[], None], x: int, y: int) -> None:
		if self.role_section.get("mouseSounds", False):
			ignored_roles = {Role.DOCUMENT, Role.WINDOW, Role.PANE, Role.APPLICATION, Role.UNKNOWN}

			if getattr(obj, "role", None) not in ignored_roles and obj != getattr(self, "_last_mouse_obj", None):
				now = time.monotonic()
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
		# Roles/states are only silenced for the reasons that play sounds;
		# all other reasons keep announcing them so context is never lost.
		if _reason_plays_nav_sounds(reason):
			try:
				self._filter_announced_properties(kwargs)
			except Exception:
				log.debugWarning("NavigationSounds: property speech filtering failed", exc_info=True)

		if hasattr(self, "old_getPropertiesSpeech") and self.old_getPropertiesSpeech is not None:
			return self.old_getPropertiesSpeech(reason, **kwargs)
		return []

	def _filter_announced_properties(self, kwargs: dict[str, Any]) -> None:
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
					kwargs.update({k: (states - to_remove if k == "states" else v) for k, v in kwargs.items()})
				elif isinstance(states, list):
					kwargs.update({
						k: ([s for s in states if s not in to_remove] if k == "states" else v)
						for k, v in kwargs.items()
					})

	@script(gesture="kb:NVDA+alt+n")
	def script_toggle(self, unused_gesture: inputCore.InputGesture) -> None:
		cfg_typing = self.role_section["typing"]
		is_same_script = getLastScriptRepeatCount()

		if is_same_script == 0:
			self.cfg_sounds = not self.cfg_sounds
			if self.cfg_sounds is False:
				ui.message(_("Disable navigation sounds"))
				# Listener start/stop already swallow and log their own errors.
				self.browser_interceptor.terminate()
			else:
				ui.message(_("Enable navigation sounds"))
				self.browser_interceptor.patch()

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
		if (
			hasattr(self, "_speech_module")
			and hasattr(self, "_speech_attr")
			and hasattr(self, "old_getPropertiesSpeech")
		):
			try:
				setattr(self._speech_module, self._speech_attr, self.old_getPropertiesSpeech)
			except Exception:
				log.debugWarning("Failed to restore patched getPropertiesSpeech", exc_info=True)
		elif hasattr(self, "old_getPropertiesSpeech") and self.old_getPropertiesSpeech is not None:
			try:
				speech.speech.getPropertiesSpeech = self.old_getPropertiesSpeech
			except Exception:
				log.debugWarning("Failed to restore legacy getPropertiesSpeech", exc_info=True)

		if hasattr(self, "_old_speech_pkg_fn") and self._old_speech_pkg_fn is not None:
			try:
				speech.getPropertiesSpeech = self._old_speech_pkg_fn
			except Exception:
				log.debugWarning("Failed to restore package-level getPropertiesSpeech", exc_info=True)

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
