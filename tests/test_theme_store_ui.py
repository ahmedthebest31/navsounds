"""Tests for the settings panel glue around the theme store and the importer.

The panel only runs inside NVDA, so wx and the gui helpers are stubbed here.
Two helpers are exercised, both of them free of dialog code: the category
inference that pre-selects a radio button, and the merged list that fills the
theme dropdowns.
"""

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from test_plugin_nav_sound_selection import load_plugin_module
from test_theme_import import make_wav, make_zip

ROLE_NAMES = frozenset({"button", "link", "slider"})


def load_settings_module(monkeypatch):
	"""Import the plugin package first, then the settings panel built on top of it."""
	plugin_module = load_plugin_module(monkeypatch)
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


def resolve(monkeypatch, config_module=None, global_vars=None, nvda_state=None):
	"""Call the plugin's config directory resolver with only the given modules."""
	plugin_module, _ = load_settings_module(monkeypatch)
	if config_module is None:
		config_module = SimpleNamespace()
	if global_vars is None:
		global_vars = SimpleNamespace()
	return plugin_module._resolve_config_dir(config_module, global_vars, nvda_state)


def test_config_dir_comes_from_write_paths_on_current_nvda(monkeypatch):
	"""NVDA 2024 and later expose the authoritative directory as WritePaths.configDir."""
	state = SimpleNamespace(WritePaths=SimpleNamespace(configDir=r"C:\Users\me\AppData\Roaming\nvda"))
	globals_stub = SimpleNamespace(appArgs=SimpleNamespace(configPath=r"D:\override"))
	assert str(resolve(monkeypatch, global_vars=globals_stub, nvda_state=state)) == str(
		Path(r"C:\Users\me\AppData\Roaming\nvda")
	)


def test_config_dir_falls_back_to_the_command_line_override(monkeypatch):
	"""A -c/--config-dir override is the effective directory when there is no WritePaths."""
	globals_stub = SimpleNamespace(appArgs=SimpleNamespace(configPath=r"D:\override"))
	assert resolve(monkeypatch, global_vars=globals_stub) == Path(r"D:\override")


def test_config_dir_falls_back_to_nvdas_own_default(monkeypatch):
	config_module = SimpleNamespace(getUserDefaultConfigPath=lambda: r"C:\config\nvda")
	globals_stub = SimpleNamespace(appArgs=SimpleNamespace(configPath=None))
	assert resolve(monkeypatch, config_module=config_module, global_vars=globals_stub) == Path(r"C:\config\nvda")


def test_config_dir_last_resort_is_the_app_dir_user_config(monkeypatch):
	globals_stub = SimpleNamespace(appArgs=SimpleNamespace(configPath=None), appDir=r"C:\nvda")
	assert resolve(monkeypatch, global_vars=globals_stub) == Path(r"C:\nvda") / "userConfig"


def test_config_dir_resolution_never_raises_on_an_unknown_nvda(monkeypatch):
	"""Every lookup is a getattr, so no module layout can turn this into a crash."""
	assert resolve(monkeypatch) == Path("userConfig")


def test_the_plugin_never_reads_the_app_args_off_the_config_manager(tmp_path, monkeypatch):
	"""config.conf.appArgs does not exist in NVDA and froze the settings dialog when used."""
	plugin_module, _ = load_settings_module(monkeypatch)
	source = Path(plugin_module.__file__).read_text(encoding="utf-8")
	assert "config.conf.appArgs" not in source


def test_a_theme_listing_failure_cannot_break_the_settings_panel(tmp_path, monkeypatch):
	"""NVDA freezes its scrolled container until a panel builds, so no exception may escape."""
	panel, settings_module = load_with_roles(monkeypatch, tmp_path)
	nav = settings_module.NAV_KIND
	make_bundled_theme(nav, "Bundled", tmp_path)

	def explode(*args, **kwargs):
		raise settings_module.ThemeImportError("directory is unreadable")

	monkeypatch.setattr(settings_module, "list_user_themes", explode)
	assert panel._theme_choices(nav) == ["Bundled"]


def record_messages(monkeypatch, settings_module) -> list:
	"""Collects what the panel would say to the user."""
	said: list = []
	monkeypatch.setattr(settings_module.ui, "message", said.append)
	return said


def record_opened(monkeypatch, settings_module, error: OSError | None = None) -> list:
	"""Replaces os.startfile so no folder is really opened during a test."""
	opened: list = []

	def fake_startfile(path):
		if error is not None:
			raise error
		opened.append(path)

	monkeypatch.setattr(settings_module.os, "startfile", fake_startfile, raising=False)
	return opened


def test_opening_the_themes_folder_creates_it_and_opens_it(tmp_path, monkeypatch):
	"""The folder may not exist yet for a user who never imported a pack."""
	panel, settings_module = load_with_roles(monkeypatch, tmp_path)
	opened = record_opened(monkeypatch, settings_module)
	expected = Path(panel.main_plugin.config_path) / "navsounds_themes"

	panel.onopenthemes(None)

	assert opened == [expected]
	assert expected.is_dir()


def test_a_failure_to_open_the_themes_folder_is_reported(tmp_path, monkeypatch):
	panel, settings_module = load_with_roles(monkeypatch, tmp_path)
	record_opened(monkeypatch, settings_module, OSError("no shell"))
	said = record_messages(monkeypatch, settings_module)

	panel.onopenthemes(None)

	assert len(said) == 1
	assert "could not be opened" in said[0]


def test_a_failure_to_open_the_bundled_folder_is_reported(tmp_path, monkeypatch):
	panel, settings_module = load_with_roles(monkeypatch, tmp_path)
	record_opened(monkeypatch, settings_module, OSError("no shell"))
	said = record_messages(monkeypatch, settings_module)

	panel.onopen(None)

	assert len(said) == 1
	assert "could not be opened" in said[0]


def test_the_settings_donate_button_offers_both_choices(tmp_path, monkeypatch):
	panel, settings_module = load_with_roles(monkeypatch, tmp_path)
	seen: list = []
	monkeypatch.setattr(
		settings_module, "show_donate_dialog", lambda parent, first_run=False: seen.append((parent, first_run))
	)

	panel.ondonate(None)

	assert seen == [(panel, False)]


def test_the_two_donation_buttons_lead_to_different_pages(monkeypatch):
	_, settings_module = load_settings_module(monkeypatch)
	dialog = settings_module.DonateDialog.__new__(settings_module.DonateDialog)
	dialog.choice = ""
	dialog.EndModal = lambda code: None

	settings_module.DonateDialog.onChoosePayPal(dialog, None)
	assert dialog.choice == settings_module.PAYPAL_URL

	settings_module.DonateDialog.onChooseInstaPay(dialog, None)
	assert dialog.choice == settings_module.INSTAPAY_URL


def test_the_reminder_opens_the_page_the_user_picked(monkeypatch, tmp_path):
	"""Drives the dialog through a stub, because wx cannot be built here."""
	_, settings_module = load_settings_module(monkeypatch)
	said = record_messages(monkeypatch, settings_module)
	opened: list = []

	class StubDialog:
		def __init__(self, parent, first_run=False):
			self.choice = settings_module.INSTAPAY_URL
			self.dont_ask = SimpleNamespace(GetValue=lambda: False)

		def __enter__(self):
			return self

		def __exit__(self, *exc_info):
			return False

		def ShowModal(self):
			return settings_module.wx.ID_OK

	monkeypatch.setattr(settings_module, "DonateDialog", StubDialog)
	monkeypatch.setattr(settings_module.web, "open", lambda url: opened.append(url) or True)

	assert settings_module.show_donate_dialog(None, first_run=True) is False
	assert opened == [settings_module.INSTAPAY_URL]
	assert said


def test_the_reminder_stops_only_when_the_box_is_ticked(monkeypatch):
	_, settings_module = load_settings_module(monkeypatch)
	monkeypatch.setattr(settings_module.web, "open", lambda url: True)

	class StubDialog:
		def __init__(self, parent, first_run=False):
			self.choice = settings_module.PAYPAL_URL
			self.dont_ask = SimpleNamespace(GetValue=lambda: True)

		def __enter__(self):
			return self

		def __exit__(self, *exc_info):
			return False

		def ShowModal(self):
			return settings_module.wx.ID_CANCEL

	monkeypatch.setattr(settings_module, "DonateDialog", StubDialog)

	assert settings_module.show_donate_dialog(None, first_run=True) is True


def test_a_donation_page_that_will_not_open_is_reported(monkeypatch):
	_, settings_module = load_settings_module(monkeypatch)
	said = record_messages(monkeypatch, settings_module)

	class StubDialog:
		def __init__(self, parent, first_run=False):
			self.choice = settings_module.PAYPAL_URL
			self.dont_ask = None

		def __enter__(self):
			return self

		def __exit__(self, *exc_info):
			return False

		def ShowModal(self):
			return settings_module.wx.ID_OK

	monkeypatch.setattr(settings_module, "DonateDialog", StubDialog)
	monkeypatch.setattr(settings_module.web, "open", lambda url: False)

	assert settings_module.show_donate_dialog(None) is False
	assert said


def test_the_reminder_is_due_only_every_thirty_days(monkeypatch):
	_, settings_module = load_settings_module(monkeypatch)
	should = settings_module.should_prompt_for_donation
	today = date(2026, 10, 4)
	assert settings_module.DONATION_PROMPT_INTERVAL_DAYS == 30
	assert should(True, "", today) is True
	assert should(False, "", today) is False
	assert should(True, "2026-09-04", today) is True
	assert should(True, "2026-09-05", today) is False
	assert should(True, "2026-10-05", today) is False
	assert should(True, "not-a-date", today) is True


def test_a_failing_reminder_never_breaks_startup(monkeypatch):
	plugin_module, _ = load_settings_module(monkeypatch)

	def explode(*args, **kwargs):
		raise RuntimeError("no GUI here")

	monkeypatch.setattr(plugin_module, "should_prompt_for_donation", explode)
	plugin_stub = SimpleNamespace(role_section={"donationPromptEnabled": True, "donationPromptLastShown": ""})

	plugin_module.GlobalPlugin._maybe_prompt_for_donation(plugin_stub)

	assert plugin_stub.role_section["donationPromptLastShown"] == ""


def test_a_due_reminder_reaches_the_dialog_and_stores_the_date(monkeypatch):
	plugin_module, _ = load_settings_module(monkeypatch)
	shown = []

	def record(parent, first_run=False):
		shown.append((parent, first_run))
		return False

	monkeypatch.setattr(plugin_module, "show_donate_dialog", record)
	plugin_stub = SimpleNamespace(role_section={"donationPromptEnabled": True, "donationPromptLastShown": ""})

	plugin_module.GlobalPlugin._maybe_prompt_for_donation(plugin_stub)

	assert shown == [(None, True)]
	assert plugin_stub.role_section["donationPromptLastShown"] == date.today().isoformat()
	assert plugin_stub.role_section["donationPromptEnabled"] is True


def test_the_reminder_is_deferred_to_the_wx_event_loop():
	"""guiHelper has no runOnceAsync; that invented API stopped the add-on from loading at all."""
	source = Path(__file__).resolve().parent.parent / "navsounds" / "globalPlugins" / "NavigationSounds" / "__init__.py"
	text = source.read_text(encoding="utf-8")

	assert "wx.CallAfter(self._maybe_prompt_for_donation)" in text
	assert "runOnceAsync" not in text
