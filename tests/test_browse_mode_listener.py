import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


class FakeAction:
	def __init__(self):
		self.handlers = []

	def register(self, handler):
		self.handlers.append(handler)

	def unregister(self, handler):
		if handler in self.handlers:
			self.handlers.remove(handler)
			return True
		return False

	def notify(self, obj):
		for handler in list(self.handlers):
			handler(obj=obj)


class FakeTextInfo:
	def __init__(self, obj=None, focusable=None):
		self.NVDAObjectAtStart = obj
		self.focusableNVDAObjectAtStart = focusable


def load_browser_module(monkeypatch):
	fake_vision = SimpleNamespace(
		handler=SimpleNamespace(
			extensionPoints=SimpleNamespace(post_browseModeMove=FakeAction()),
		),
	)
	monkeypatch.setitem(sys.modules, "browseMode", SimpleNamespace(BrowseModeTreeInterceptor=object))
	monkeypatch.setitem(sys.modules, "cursorManager", SimpleNamespace(CursorManager=object))
	monkeypatch.setitem(sys.modules, "inputCore", SimpleNamespace(InputGesture=object))
	monkeypatch.setitem(sys.modules, "textInfos", SimpleNamespace(POSITION_CARET=object()))
	monkeypatch.setitem(
		sys.modules, "controlTypes", SimpleNamespace(Role=lambda value: value, State=lambda value: value)
	)
	monkeypatch.setitem(sys.modules, "vision", fake_vision)

	module_path = (
		Path(__file__).resolve().parents[1] / "navsounds" / "globalPlugins" / "NavigationSounds" / "browser.py"
	)
	spec = importlib.util.spec_from_file_location("navsounds_browser_under_test", module_path)
	browser = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(browser)
	return browser


def test_registers_once_and_unregisters(monkeypatch):
	browser = load_browser_module(monkeypatch)
	action = FakeAction()
	fake_vision = SimpleNamespace(
		handler=SimpleNamespace(
			extensionPoints=SimpleNamespace(post_browseModeMove=action),
		),
	)
	monkeypatch.setattr(browser, "vision", fake_vision)

	listener = browser.BrowseModeMoveListener(SimpleNamespace(_play_nav_for_object=lambda obj: None))
	listener.start()
	listener.start()

	assert action.handlers == [listener._on_browse_mode_move]

	listener.stop()
	assert action.handlers == []


def test_notify_plays_object_at_caret(monkeypatch):
	browser = load_browser_module(monkeypatch)
	action = FakeAction()
	fake_vision = SimpleNamespace(
		handler=SimpleNamespace(
			extensionPoints=SimpleNamespace(post_browseModeMove=action),
		),
	)
	monkeypatch.setattr(browser, "vision", fake_vision)
	monkeypatch.setattr(browser.textInfos, "POSITION_CARET", object())

	caret_obj = SimpleNamespace(role="link")
	cursor_manager = SimpleNamespace(
		makeTextInfo=lambda position: FakeTextInfo(obj=caret_obj),
		currentNVDAObject=SimpleNamespace(role="document"),
	)
	played = []

	listener = browser.BrowseModeMoveListener(SimpleNamespace(cfg_sounds=True, _play_nav_for_object=played.append))
	listener.start()
	action.notify(cursor_manager)

	assert played == [caret_obj]


def test_positional_notify_plays_object_at_caret(monkeypatch):
	browser = load_browser_module(monkeypatch)
	action = FakeAction()
	fake_vision = SimpleNamespace(
		handler=SimpleNamespace(
			extensionPoints=SimpleNamespace(post_browseModeMove=action),
		),
	)
	monkeypatch.setattr(browser, "vision", fake_vision)

	caret_obj = SimpleNamespace(role="link")
	cursor_manager = SimpleNamespace(makeTextInfo=lambda position: FakeTextInfo(obj=caret_obj))
	played = []

	listener = browser.BrowseModeMoveListener(SimpleNamespace(cfg_sounds=True, _play_nav_for_object=played.append))
	listener.start()
	action.handlers[0](cursor_manager)

	assert played == [caret_obj]


def test_browse_mode_handler_swallows_plugin_errors(monkeypatch):
	browser = load_browser_module(monkeypatch)
	action = FakeAction()
	fake_vision = SimpleNamespace(
		handler=SimpleNamespace(
			extensionPoints=SimpleNamespace(post_browseModeMove=action),
		),
	)
	monkeypatch.setattr(browser, "vision", fake_vision)

	caret_obj = SimpleNamespace(role="link")
	cursor_manager = SimpleNamespace(makeTextInfo=lambda position: FakeTextInfo(obj=caret_obj))

	def fail(obj):
		raise RuntimeError("sound dispatch failed")

	listener = browser.BrowseModeMoveListener(SimpleNamespace(cfg_sounds=True, _play_nav_for_object=fail))
	listener.start()
	action.notify(cursor_manager)


def test_object_at_caret_prefers_nvda_object_over_focusable(monkeypatch):
	browser = load_browser_module(monkeypatch)
	caret_obj = SimpleNamespace(role="heading")
	focusable_obj = SimpleNamespace(role="button")
	cursor_manager = SimpleNamespace(
		makeTextInfo=lambda position: FakeTextInfo(obj=caret_obj, focusable=focusable_obj),
		currentNVDAObject=SimpleNamespace(role="document"),
	)

	listener = browser.BrowseModeMoveListener(SimpleNamespace(cfg_sounds=True, _play_nav_for_object=lambda obj: None))

	assert listener._get_object_at_caret(cursor_manager) is caret_obj


def test_start_is_noop_when_vision_extension_point_is_missing(monkeypatch):
	browser = load_browser_module(monkeypatch)
	monkeypatch.setattr(browser, "vision", None)
	listener = browser.BrowseModeMoveListener(SimpleNamespace(cfg_sounds=True, _play_nav_for_object=lambda obj: None))

	listener.start()

	assert listener._registered is False
