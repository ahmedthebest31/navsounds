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
	monkeypatch.setitem(sys.modules, "NVDAObjects", SimpleNamespace(NVDAObject=object, controlTypes=SimpleNamespace()))
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
		sys.modules, "logHandler", SimpleNamespace(log=SimpleNamespace(error=lambda *args, **kwargs: None))
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

	def check_and_play(name):
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

	def check_and_play(name):
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
