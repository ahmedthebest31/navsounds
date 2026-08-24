import sys
import builtins
from types import SimpleNamespace


class FakeState:
	EDITABLE = "editable"
	READONLY = "readonly"

	def __init__(self, value):
		self.value = value
		self.name = str(value).upper()


class FakeRole:
	def __init__(self, value):
		self.value = value
		self.name = str(value).upper()


class FakeConfig(dict):
	def __init__(self):
		super().__init__({"audio": {}, "speech": {}})
		self.spec = {}


def load_plugin_module(monkeypatch, speech_module=None):
	class FakeGlobalPlugin:
		def __init__(self, *args, **kwargs):
			pass

		def terminate(self):
			pass

	def identity_script(*args, **kwargs):
		def decorator(func):
			return func

		return decorator

	monkeypatch.setattr(builtins, "_", lambda value: value, raising=False)
	monkeypatch.setitem(sys.modules, "addonHandler", SimpleNamespace(initTranslation=lambda: None))
	monkeypatch.setitem(sys.modules, "api", SimpleNamespace(getMouseObject=lambda: None))
	monkeypatch.setitem(sys.modules, "config", SimpleNamespace(conf=FakeConfig()))
	monkeypatch.setitem(
		sys.modules,
		"controlTypes",
		SimpleNamespace(OutputReason=SimpleNamespace(QUERY="query"), Role=FakeRole, State=FakeState),
	)
	monkeypatch.setitem(sys.modules, "globalPluginHandler", SimpleNamespace(GlobalPlugin=FakeGlobalPlugin))
	monkeypatch.setitem(sys.modules, "gui", SimpleNamespace(guiHelper=SimpleNamespace()))
	monkeypatch.setitem(
		sys.modules,
		"gui.settingsDialogs",
		SimpleNamespace(NVDASettingsDialog=SimpleNamespace(categoryClasses=[]), SettingsPanel=object),
	)
	monkeypatch.setitem(sys.modules, "inputCore", SimpleNamespace(InputGesture=object))
	monkeypatch.setitem(
		sys.modules,
		"NVDAObjects",
		SimpleNamespace(NVDAObject=object, controlTypes=SimpleNamespace(OutputReason=SimpleNamespace(QUERY="query"))),
	)
	monkeypatch.setitem(
		sys.modules,
		"scriptHandler",
		SimpleNamespace(script=identity_script, getLastScriptRepeatCount=lambda: 0),
	)
	if speech_module is None:
		speech_module = SimpleNamespace(getPropertiesSpeech=lambda reason, **kwargs: [])
	monkeypatch.setitem(sys.modules, "speech", speech_module)
	monkeypatch.setitem(sys.modules, "speech.commands", SimpleNamespace(SpeechCommand=object))
	monkeypatch.setitem(sys.modules, "ui", SimpleNamespace(message=lambda message: None))
	monkeypatch.setitem(sys.modules, "wx", SimpleNamespace(Sizer=object, Event=object, SL_HORIZONTAL=0))
	monkeypatch.setitem(
		sys.modules,
		"logHandler",
		SimpleNamespace(
			log=SimpleNamespace(
				error=lambda *args, **kwargs: None,
				warning=lambda *args, **kwargs: None,
				debug=lambda *args, **kwargs: None,
				debugWarning=lambda *args, **kwargs: None,
			)
		),
	)
	monkeypatch.setitem(sys.modules, "nvwave", SimpleNamespace(WavePlayer=object))
	monkeypatch.setitem(sys.modules, "browseMode", SimpleNamespace(BrowseModeTreeInterceptor=object))
	monkeypatch.setitem(sys.modules, "cursorManager", SimpleNamespace(CursorManager=object))
	monkeypatch.setitem(sys.modules, "textInfos", SimpleNamespace(POSITION_CARET="caret"))
	monkeypatch.setitem(
		sys.modules,
		"vision",
		SimpleNamespace(
			handler=SimpleNamespace(
				extensionPoints=SimpleNamespace(post_browseModeMove=SimpleNamespace()),
			),
		),
	)

	for module_name in list(sys.modules):
		if module_name.startswith("navsounds.globalPlugins.NavigationSounds"):
			monkeypatch.delitem(sys.modules, module_name, raising=False)

	import navsounds.globalPlugins.NavigationSounds as plugin_module

	return plugin_module


def test_play_nav_for_object_prefers_first_state_sound(monkeypatch):
	plugin_module = load_plugin_module(monkeypatch)

	played = []
	nav_sounds = {"nav_pressed", "nav_button"}

	def check_and_play(name, obj=None):
		sound_id = f"nav_{name}"
		if sound_id in nav_sounds:
			played.append(sound_id)
			return True
		return False

	plugin = SimpleNamespace(
		cfg_sounds=True,
		_check_and_play_nav=check_and_play,
		_last_nav_time=0.0,
	)

	plugin_module.GlobalPlugin._play_nav_for_object(
		plugin,
		SimpleNamespace(states=["pressed"], role="button"),
	)

	assert played == ["nav_pressed"]


def test_play_nav_for_object_falls_back_to_role(monkeypatch):
	plugin_module = load_plugin_module(monkeypatch)

	played = []
	nav_sounds = {"nav_button"}

	def check_and_play(name, obj=None):
		sound_id = f"nav_{name}"
		if sound_id in nav_sounds:
			played.append(sound_id)
			return True
		return False

	plugin = SimpleNamespace(
		cfg_sounds=True,
		_check_and_play_nav=check_and_play,
		_last_nav_time=0.0,
	)

	plugin_module.GlobalPlugin._play_nav_for_object(
		plugin,
		SimpleNamespace(states=["focused"], role="button"),
	)

	assert played == ["nav_button"]


def test_get_properties_speech_target_supports_modern_speech_module(monkeypatch):
	modern = SimpleNamespace(getPropertiesSpeech=lambda reason, **kwargs: ["modern"])
	plugin_module = load_plugin_module(monkeypatch, speech_module=modern)

	owner, attr, original = plugin_module.GlobalPlugin._get_properties_speech_target()

	assert owner is modern
	assert attr == "getPropertiesSpeech"
	assert original("query") == ["modern"]


def test_get_properties_speech_target_supports_legacy_nested_module(monkeypatch):
	legacy_inner = SimpleNamespace(getPropertiesSpeech=lambda reason, **kwargs: ["legacy"])
	legacy = SimpleNamespace(speech=legacy_inner)
	plugin_module = load_plugin_module(monkeypatch, speech_module=legacy)

	owner, attr, original = plugin_module.GlobalPlugin._get_properties_speech_target()

	assert owner is legacy_inner
	assert attr == "getPropertiesSpeech"
	assert original("query") == ["legacy"]


class _Reason:
	def __init__(self, name):
		self.name = name


def test_reason_gate_matches_sound_reasons_by_name(monkeypatch):
	plugin_module = load_plugin_module(monkeypatch)

	gate = plugin_module._reason_plays_nav_sounds

	assert gate(_Reason("FOCUS"))
	assert gate(_Reason("CARET"))
	assert gate(_Reason("QUICKNAV"))
	assert not gate(_Reason("QUERY"))
	assert not gate(_Reason("SAYALL"))
	assert gate("caret")
	assert gate("controlTypes.OutputReason.FOCUS")
	assert not gate(123)


def _make_suppression_host(plugin_module):
	"""Build a host object carrying the REAL speech methods under test."""

	class Host:
		say_roles = False
		say_states = False
		nav_sounds = {"nav_button", "nav_checked"}

		def old_getPropertiesSpeech(self, reason, **kwargs):
			return sorted(kwargs.keys()) + ["ORIG"]

	Host.get_property2_speech = plugin_module.GlobalPlugin.get_property2_speech
	Host._filter_announced_properties = plugin_module.GlobalPlugin._filter_announced_properties
	return Host()


def test_roles_and_states_suppressed_for_focus_reason(monkeypatch):
	plugin_module = load_plugin_module(monkeypatch)
	host = _make_suppression_host(plugin_module)

	result = host.get_property2_speech(
		reason=_Reason("FOCUS"),
		role="button",
		states=["checked"],
	)

	assert "role" not in result
	assert "states" in result
	assert "ORIG" in result


def test_roles_and_states_kept_for_query_reason(monkeypatch):
	plugin_module = load_plugin_module(monkeypatch)
	host = _make_suppression_host(plugin_module)

	result = host.get_property2_speech(
		reason=_Reason("QUERY"),
		role="button",
		states=["checked"],
	)

	assert "role" in result
	assert "states" in result


def _make_play_nav_host(plugin_module, cfg_sounds=True):
	played = []

	class Host:
		pass

	host = Host()
	host.cfg_sounds = cfg_sounds
	host.audio_manager = SimpleNamespace(play=played.append)
	Host.play_nav = plugin_module.GlobalPlugin.play_nav
	return host, played


def test_play_nav_suppresses_same_object_within_window(monkeypatch):
	plugin_module = load_plugin_module(monkeypatch)
	clock = {"now": 1000.0}
	monkeypatch.setattr(plugin_module.time, "monotonic", lambda: clock["now"])

	host, played = _make_play_nav_host(plugin_module)
	first = SimpleNamespace(role="button")
	second = SimpleNamespace(role="button")

	host.play_nav("nav_button", first)
	clock["now"] += 0.05
	host.play_nav("nav_button", first)
	clock["now"] += 0.15
	host.play_nav("nav_button", second)
	clock["now"] += 0.10
	host.play_nav("nav_button", second)
	clock["now"] += 0.40
	host.play_nav("nav_button", second)

	assert played == ["nav_button", "nav_button", "nav_button"]


def test_play_nav_without_object_keeps_short_throttle(monkeypatch):
	plugin_module = load_plugin_module(monkeypatch)
	clock = {"now": 2000.0}
	monkeypatch.setattr(plugin_module.time, "monotonic", lambda: clock["now"])

	host, played = _make_play_nav_host(plugin_module)

	host.play_nav("nav_link")
	clock["now"] += 0.02
	host.play_nav("nav_link")
	clock["now"] += 0.30
	host.play_nav("nav_link")

	assert played == ["nav_link", "nav_link"]


def test_play_nav_respects_master_switch(monkeypatch):
	plugin_module = load_plugin_module(monkeypatch)
	clock = {"now": 3000.0}
	monkeypatch.setattr(plugin_module.time, "monotonic", lambda: clock["now"])

	host, played = _make_play_nav_host(plugin_module, cfg_sounds=False)

	host.play_nav("nav_heading", SimpleNamespace(role="heading"))
	host.play_nav("nav_heading")

	assert played == []
