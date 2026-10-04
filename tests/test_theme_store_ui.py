"""Tests for the settings panel glue around the theme store and the importer.

The panel only runs inside NVDA, so wx and the gui helpers are stubbed here.
Two helpers are exercised, both of them free of dialog code: the category
inference that pre-selects a radio button, and the merged list that fills the
theme dropdowns.
"""

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

from test_plugin_nav_sound_selection import load_plugin_module
from test_theme_import import make_wav, make_zip

ROLE_NAMES = frozenset({"button", "link", "slider"})


class FakeWx(ModuleType):
	"""Stands in for wx: every attribute resolves to a fresh dummy class."""

	def __getattr__(self, name: str):
		value = type(name, (), {})
		setattr(self, name, value)
		return value


def load_settings_module(monkeypatch):
	"""Import the plugin package first, then the settings panel built on top of it."""
	plugin_module = load_plugin_module(monkeypatch)
	monkeypatch.setitem(sys.modules, "wx", FakeWx("wx"))
	import navsounds.globalPlugins.NavigationSounds.settings as settings_module

	return plugin_module, settings_module


def make_panel(plugin_module, settings_module, tmp_path: Path):
	"""Build a panel carrying only what the helpers under test read."""
	plugin_stub = SimpleNamespace()

	def is_role_sound_name(stem: str) -> bool:
		return plugin_module.GlobalPlugin.is_role_sound_name(plugin_stub, stem)

	panel = settings_module.NavSettingsPanel.__new__(settings_module.NavSettingsPanel)
	panel.main_plugin = SimpleNamespace(
		config_path=tmp_path / "config",
		main_paths=tmp_path / "addon",
		is_role_sound_name=is_role_sound_name,
	)
	return panel


def make_bundled_theme(kind: str, name: str, tmp_path: Path) -> None:
	(tmp_path / "addon" / "effects" / kind / name).mkdir(parents=True)


def import_theme(settings_module, panel, archive: Path, kind: str) -> None:
	settings_module.import_theme_zip(archive, panel.main_plugin.config_path, kind)


def load_with_roles(monkeypatch, tmp_path: Path):
	plugin_module, settings_module = load_settings_module(monkeypatch)
	monkeypatch.setattr(plugin_module, "_ROLE_NAMES", ROLE_NAMES)
	return make_panel(plugin_module, settings_module, tmp_path), settings_module


def test_keyboard_names_are_inferred_as_a_typing_pack(tmp_path, monkeypatch):
	panel, settings_module = load_with_roles(monkeypatch, tmp_path)
	archive = make_zip(tmp_path / "keys.zip", {"key_enter.wav": make_wav(), "space.wav": make_wav()})
	assert panel._guess_theme_kind(archive) == settings_module.TYPE_KIND


def test_a_role_name_is_inferred_as_a_navigation_pack(tmp_path, monkeypatch):
	panel, settings_module = load_with_roles(monkeypatch, tmp_path)
	archive = make_zip(tmp_path / "roles.zip", {"button.wav": make_wav(), "link.wav": make_wav()})
	assert panel._guess_theme_kind(archive) == settings_module.NAV_KIND


def test_a_single_role_name_wins_over_keyboard_names(tmp_path, monkeypatch):
	panel, settings_module = load_with_roles(monkeypatch, tmp_path)
	archive = make_zip(tmp_path / "mixed.zip", {"key_enter.wav": make_wav(), "button.wav": make_wav()})
	assert panel._guess_theme_kind(archive) == settings_module.NAV_KIND


def test_a_pack_without_role_names_is_never_guessed_as_navigation(tmp_path, monkeypatch):
	panel, settings_module = load_with_roles(monkeypatch, tmp_path)
	archive = make_zip(tmp_path / "caps.zip", {"caps_lock.wav": make_wav()})
	assert panel._guess_theme_kind(archive) == settings_module.TYPE_KIND


def test_an_archive_without_audio_gives_no_guess(tmp_path, monkeypatch):
	panel, _ = load_with_roles(monkeypatch, tmp_path)
	archive = make_zip(tmp_path / "notes.zip", {"readme.txt": b"no audio in here"})
	assert panel._guess_theme_kind(archive) is None


def test_a_malformed_archive_gives_no_guess(tmp_path, monkeypatch):
	panel, _ = load_with_roles(monkeypatch, tmp_path)
	broken = tmp_path / "broken.zip"
	broken.write_bytes(b"PK this is not a real archive")
	assert panel._guess_theme_kind(broken) is None


def test_bundled_themes_are_listed_before_imported_ones(tmp_path, monkeypatch):
	panel, settings_module = load_with_roles(monkeypatch, tmp_path)
	nav = settings_module.NAV_KIND
	make_bundled_theme(nav, "Zebra", tmp_path)
	make_bundled_theme(nav, "Alpha", tmp_path)
	import_theme(settings_module, panel, make_zip(tmp_path / "one.zip", {"beta pack/key.wav": make_wav()}), nav)
	import_theme(settings_module, panel, make_zip(tmp_path / "two.zip", {"zebra/key.wav": make_wav()}), nav)
	assert panel._theme_choices(nav) == ["Alpha", "Zebra", "beta pack"]


def test_a_bundled_theme_is_never_replaced_by_an_imported_twin(tmp_path, monkeypatch):
	panel, settings_module = load_with_roles(monkeypatch, tmp_path)
	nav = settings_module.NAV_KIND
	make_bundled_theme(nav, "Zebra", tmp_path)
	import_theme(settings_module, panel, make_zip(tmp_path / "one.zip", {"zebra/key.wav": make_wav()}), nav)
	assert panel._theme_choices(nav) == ["Zebra"]


def test_case_colliding_imports_both_stay_selectable(tmp_path, monkeypatch):
	"""The importer renames a case collision, so both folders are real themes."""
	panel, settings_module = load_with_roles(monkeypatch, tmp_path)
	nav = settings_module.NAV_KIND
	import_theme(settings_module, panel, make_zip(tmp_path / "one.zip", {"Alpha pack/key.wav": make_wav()}), nav)
	import_theme(settings_module, panel, make_zip(tmp_path / "two.zip", {"alpha pack/key.wav": make_wav()}), nav)
	assert panel._theme_choices(nav) == ["Alpha pack", "alpha pack (1)"]


def test_the_two_categories_keep_separate_lists(tmp_path, monkeypatch):
	panel, settings_module = load_with_roles(monkeypatch, tmp_path)
	make_bundled_theme(settings_module.NAV_KIND, "Nav pack", tmp_path)
	import_theme(
		settings_module,
		panel,
		make_zip(tmp_path / "keys.zip", {"Type pack/key.wav": make_wav()}),
		settings_module.TYPE_KIND,
	)
	assert panel._theme_choices(settings_module.NAV_KIND) == ["Nav pack"]
	assert panel._theme_choices(settings_module.TYPE_KIND) == ["Type pack"]


def test_a_dropdown_starts_with_only_the_bundled_themes(tmp_path, monkeypatch):
	panel, settings_module = load_with_roles(monkeypatch, tmp_path)
	make_bundled_theme(settings_module.TYPE_KIND, "Classic Typewriter", tmp_path)
	assert panel._theme_choices(settings_module.TYPE_KIND) == ["Classic Typewriter"]
	assert panel._theme_choices(settings_module.NAV_KIND) == []
