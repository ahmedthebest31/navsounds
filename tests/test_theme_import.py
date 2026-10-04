"""Tests for the theme import engine.

theme_import deliberately imports nothing from NVDA, so it is loaded straight
from its file. That keeps these tests free of the sys.modules stubbing the
other suites need, and it also proves the module has no hidden NVDA dependency.
"""

import importlib.util
import io
import os
import wave
import zipfile
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parent.parent / "navsounds" / "globalPlugins" / "NavigationSounds" / "theme_import.py"
_spec = importlib.util.spec_from_file_location("navsounds_theme_import", MODULE_PATH)
theme_import = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(theme_import)

NAV = theme_import.NAV_KIND
TYPE = theme_import.TYPE_KIND


def make_wav(frames: int = 8, rate: int = 8000) -> bytes:
	"""Build a small but genuinely decodable mono PCM wav in memory."""
	buffer = io.BytesIO()
	with wave.open(buffer, "wb") as writer:
		writer.setnchannels(1)
		writer.setsampwidth(2)
		writer.setframerate(rate)
		writer.writeframes(b"\x00\x00" * frames)
	return buffer.getvalue()


def make_zip(path: Path, files: dict[str, bytes]) -> Path:
	"""Write a zip with the exact member names given, nesting included."""
	with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
		for name, data in files.items():
			archive.writestr(name, data)
	return path


def user_root(tmp_path: Path) -> Path:
	return theme_import.get_user_themes_root(tmp_path)


def stray_temp_dirs(root: Path) -> list[Path]:
	if not root.is_dir():
		return []
	return [entry for entry in root.iterdir() if entry.is_dir() and entry.name.startswith(".import-")]


def test_flat_archive_uses_archive_name_and_installs_files_directly(tmp_path):
	archive = make_zip(tmp_path / "Wooden Blocks.zip", {"button.wav": make_wav(), "checkbox.wav": make_wav()})

	result = theme_import.import_theme_zip(archive, tmp_path, NAV)

	assert result.theme_name == "Wooden Blocks"
	assert result.kind == NAV
	assert result.file_count == 2
	assert result.skipped_count == 0
	assert result.destination == user_root(tmp_path) / NAV / "Wooden Blocks"
	assert sorted(p.name for p in result.destination.iterdir()) == ["button.wav", "checkbox.wav"]


def test_deeply_nested_archive_is_flattened_to_the_theme_folder(tmp_path):
	archive = make_zip(
		tmp_path / "deep.zip",
		{
			"empty_folder/release/build/2019/Deep Pack/button.wav": make_wav(),
			"empty_folder/release/build/2019/Deep Pack/link.wav": make_wav(),
			"empty_folder/readme.txt": b"ignore me",
		},
	)

	result = theme_import.import_theme_zip(archive, tmp_path, NAV)

	assert result.theme_name == "Deep Pack"
	assert result.file_count == 2
	installed = sorted(p.name for p in result.destination.iterdir())
	assert installed == ["button.wav", "link.wav"]
	assert all(p.is_file() for p in result.destination.iterdir())


def test_single_wrapping_folder_names_the_theme_and_keeps_spaces(tmp_path):
	archive = make_zip(
		tmp_path / "pack.zip", {"Classic Typewriter/s.wav": make_wav(), "Classic Typewriter/bill.wav": make_wav()}
	)

	result = theme_import.import_theme_zip(archive, tmp_path, TYPE)

	assert result.theme_name == "Classic Typewriter"
	assert result.destination == user_root(tmp_path) / TYPE / "Classic Typewriter"


def test_files_at_root_together_with_a_folder_fall_back_to_the_archive_name(tmp_path):
	archive = make_zip(
		tmp_path / "Mixed.zip",
		{"button.wav": make_wav(), "extras/link.wav": make_wav()},
	)

	result = theme_import.import_theme_zip(archive, tmp_path, NAV)

	assert result.theme_name == "Mixed"


def test_duplicate_name_resolves_with_an_incremental_suffix(tmp_path):
	existing = user_root(tmp_path) / NAV / "TalkBack"
	existing.mkdir(parents=True)
	(existing / "button.wav").write_bytes(make_wav())
	archive = make_zip(tmp_path / "TalkBack.zip", {"TalkBack/button.wav": make_wav()})

	first = theme_import.import_theme_zip(archive, tmp_path, NAV)
	second = theme_import.import_theme_zip(archive, tmp_path, NAV)
	third = theme_import.import_theme_zip(archive, tmp_path, NAV)

	assert first.theme_name == "TalkBack (1)"
	assert second.theme_name == "TalkBack (2)"
	assert third.theme_name == "TalkBack (3)"
	assert (existing / "button.wav").read_bytes() == make_wav()


def test_builtin_theme_names_are_never_shadowed(tmp_path):
	archive = make_zip(tmp_path / "default.zip", {"button.wav": make_wav()})

	result = theme_import.import_theme_zip(archive, tmp_path, NAV, builtin_theme_names=["default", "TalkBack"])

	assert result.theme_name == "default (1)"


def test_builtin_name_collision_is_case_insensitive(tmp_path):
	archive = make_zip(tmp_path / "talkback.zip", {"button.wav": make_wav()})

	result = theme_import.import_theme_zip(archive, tmp_path, NAV, builtin_theme_names=["TalkBack"])

	assert result.theme_name == "talkback (1)"


def test_typing_and_navigation_namespaces_do_not_collide(tmp_path):
	archive = make_zip(tmp_path / "key1.zip", {"key1.wav": make_wav()})

	nav_result = theme_import.import_theme_zip(archive, tmp_path, NAV)
	type_result = theme_import.import_theme_zip(archive, tmp_path, TYPE)

	assert nav_result.theme_name == "key1"
	assert type_result.theme_name == "key1"


@pytest.mark.parametrize(
	"member",
	["../../escaped.wav", "nested/../../escaped.wav", "/absolute.wav", "C:/windows/escaped.wav", "..\\..\\escaped.wav"],
)
def test_zip_slip_attempts_are_rejected_and_write_nothing(tmp_path, member):
	archive = make_zip(tmp_path / "evil.zip", {member: make_wav(), "fine/button.wav": make_wav()})

	with pytest.raises(theme_import.ThemeImportError):
		theme_import.import_theme_zip(archive, tmp_path, NAV)

	assert not (tmp_path / "escaped.wav").exists()
	assert not (tmp_path.parent / "escaped.wav").exists()
	assert stray_temp_dirs(user_root(tmp_path)) == []


def test_absolute_member_does_not_stop_extraction_because_the_write_is_flattened(tmp_path):
	"""A traversal member never reaches the filesystem; extraction keeps going."""
	archive = make_zip(tmp_path / "ok.zip", {"button.wav": make_wav()})

	result = theme_import.import_theme_zip(archive, tmp_path, NAV)

	assert result.file_count == 1
	assert (result.destination / "button.wav").is_file()


def test_os_junk_and_non_audio_files_are_stripped(tmp_path):
	archive = make_zip(
		tmp_path / "Junky.zip",
		{
			"Junky/button.wav": make_wav(),
			"Junky/.DS_Store": b"mac junk",
			"Junky/Thumbs.db": b"windows junk",
			"Junky/desktop.ini": b"windows junk",
			"Junky/notes.txt": b"readme text",
			"__MACOSX/Junky/._button.wav": b"resource fork",
			"__MACOSX/Junky/.DS_Store": b"mac junk",
		},
	)

	result = theme_import.import_theme_zip(archive, tmp_path, NAV)

	assert [p.name for p in result.destination.iterdir()] == ["button.wav"]


def test_empty_archive_is_rejected_and_leaves_nothing_behind(tmp_path):
	archive = make_zip(tmp_path / "empty.zip", {})

	with pytest.raises(theme_import.ThemeImportError):
		theme_import.import_theme_zip(archive, tmp_path, NAV)

	assert stray_temp_dirs(user_root(tmp_path)) == []


def test_archive_without_audio_is_rejected(tmp_path):
	archive = make_zip(tmp_path / "docs.zip", {"readme.md": b"# hello", "src/main.py": b"print()"})

	with pytest.raises(theme_import.ThemeImportError):
		theme_import.import_theme_zip(archive, tmp_path, NAV)

	assert not (user_root(tmp_path) / NAV).exists()


def test_malformed_archive_is_rejected(tmp_path):
	broken = tmp_path / "broken.zip"
	broken.write_bytes(b"PK\x03\x04 this is not a real archive")

	with pytest.raises(theme_import.ThemeImportError):
		theme_import.import_theme_zip(broken, tmp_path, NAV)

	assert stray_temp_dirs(user_root(tmp_path)) == []


def test_missing_archive_is_rejected(tmp_path):
	with pytest.raises(theme_import.ThemeImportError):
		theme_import.import_theme_zip(tmp_path / "absent.zip", tmp_path, NAV)


def test_one_unreadable_file_does_not_lose_the_theme(tmp_path):
	archive = make_zip(
		tmp_path / "Partly Broken.zip",
		{"Pack/button.wav": make_wav(), "Pack/link.wav": b"RIFF not really a wav at all"},
	)

	result = theme_import.import_theme_zip(archive, tmp_path, NAV)

	assert result.file_count == 1
	assert result.skipped_count == 1
	assert [p.name for p in result.destination.iterdir()] == ["button.wav"]


def test_theme_of_only_unreadable_files_is_rejected(tmp_path):
	archive = make_zip(tmp_path / "Broken.zip", {"Pack/button.wav": b"garbage", "Pack/link.wav": b"garbage"})

	with pytest.raises(theme_import.ThemeImportError):
		theme_import.import_theme_zip(archive, tmp_path, NAV)

	assert not (user_root(tmp_path) / NAV / "Broken").exists()
	assert stray_temp_dirs(user_root(tmp_path)) == []


def test_header_only_wav_with_zero_frames_is_treated_as_unusable(tmp_path):
	buffer = io.BytesIO()
	with wave.open(buffer, "wb") as writer:
		writer.setnchannels(1)
		writer.setsampwidth(2)
		writer.setframerate(8000)
		writer.writeframes(b"")
	archive = make_zip(tmp_path / "Silent.zip", {"Silent/button.wav": buffer.getvalue()})

	with pytest.raises(theme_import.ThemeImportError):
		theme_import.import_theme_zip(archive, tmp_path, NAV)


def test_unsupported_sample_width_is_treated_as_unusable(tmp_path):
	buffer = io.BytesIO()
	with wave.open(buffer, "wb") as writer:
		writer.setnchannels(1)
		writer.setsampwidth(3)
		writer.setframerate(8000)
		writer.writeframes(b"\x00\x00\x00" * 8)
	archive = make_zip(tmp_path / "Wide.zip", {"Wide/button.wav": buffer.getvalue(), "Wide/link.wav": make_wav()})

	result = theme_import.import_theme_zip(archive, tmp_path, NAV)

	assert result.file_count == 1
	assert result.skipped_count == 1


def test_names_differing_only_in_case_keep_a_single_sound(tmp_path):
	archive = make_zip(tmp_path / "Case.zip", {"Case/Button.wav": make_wav(), "Case/button.wav": make_wav()})

	result = theme_import.import_theme_zip(archive, tmp_path, NAV)

	assert result.file_count == 1
	assert len(list(result.destination.iterdir())) == 1


def test_uppercase_extension_is_accepted(tmp_path):
	archive = make_zip(tmp_path / "Shouty.zip", {"Shouty/BUTTON.WAV": make_wav()})

	result = theme_import.import_theme_zip(archive, tmp_path, NAV)

	assert [p.name for p in result.destination.iterdir()] == ["BUTTON.WAV"]


def test_non_ascii_theme_name_survives(tmp_path):
	archive = make_zip(tmp_path / "Pack.zip", {"PACK Ünïcode/keypress.wav": make_wav()})

	result = theme_import.import_theme_zip(archive, tmp_path, TYPE)

	assert result.theme_name == "PACK Ünïcode"


def test_windows_illegal_characters_are_stripped_from_the_name(tmp_path):
	archive = make_zip(tmp_path / "Pack.zip", {"we:ird</button.wav": make_wav()})

	result = theme_import.import_theme_zip(archive, tmp_path, NAV)

	assert result.theme_name == "we ird"
	assert result.destination.name == "we ird"


def test_oversized_archive_is_refused_before_the_disk_fills(tmp_path, monkeypatch):
	archive = make_zip(tmp_path / "Huge.zip", {"Huge/button.wav": make_wav()})
	monkeypatch.setattr(theme_import, "MAX_TOTAL_BYTES", 8)

	with pytest.raises(theme_import.ThemeImportError):
		theme_import.import_theme_zip(archive, tmp_path, NAV)

	assert stray_temp_dirs(user_root(tmp_path)) == []


def test_too_many_entries_is_refused(tmp_path, monkeypatch):
	archive = make_zip(tmp_path / "Many.zip", {f"Many/s{index}.wav": make_wav() for index in range(10)})
	monkeypatch.setattr(theme_import, "MAX_ARCHIVE_ENTRIES", 5)

	with pytest.raises(theme_import.ThemeImportError):
		theme_import.import_theme_zip(archive, tmp_path, NAV)


def test_unknown_kind_is_a_programming_error_not_a_user_error(tmp_path):
	archive = make_zip(tmp_path / "Pack.zip", {"Pack/button.wav": make_wav()})

	with pytest.raises(ValueError, match="unknown sound theme kind"):
		theme_import.import_theme_zip(archive, tmp_path, "sounds")


def test_list_user_themes_reports_only_folders(tmp_path):
	archive = make_zip(tmp_path / "Pack.zip", {"Pack/button.wav": make_wav()})
	theme_import.import_theme_zip(archive, tmp_path, NAV)
	(user_root(tmp_path) / NAV / "loose.wav").write_bytes(make_wav())

	nav_themes = theme_import.list_user_themes(tmp_path, NAV)

	assert list(nav_themes) == ["Pack"]
	assert nav_themes["Pack"].is_dir()


def test_list_user_themes_is_empty_before_any_import(tmp_path):
	assert theme_import.list_user_themes(tmp_path, NAV) == {}
	assert theme_import.list_user_themes(tmp_path, TYPE) == {}


def test_list_user_themes_rejects_an_unknown_kind(tmp_path):
	with pytest.raises(ValueError, match="unknown sound theme kind"):
		theme_import.list_user_themes(tmp_path, "sounds")


def test_read_archive_wav_stems_returns_lowercased_stems_including_junk_paths(tmp_path):
	archive = make_zip(
		tmp_path / "Stems.zip",
		{"Stems/Button.WAV": make_wav(), "Stems/CHECKMENUITEM.wav": make_wav(), "__MACOSX/Stems/._x.wav": b"junk"},
	)

	stems = theme_import.read_archive_wav_stems(archive)

	assert sorted(stems) == ["button", "checkmenuitem"]


def test_read_archive_wav_stems_rejects_a_malformed_archive(tmp_path):
	broken = tmp_path / "broken.zip"
	broken.write_bytes(b"not a zip")

	with pytest.raises(theme_import.ThemeImportError):
		theme_import.read_archive_wav_stems(broken)


def test_user_themes_root_sits_inside_the_config_path(tmp_path):
	root = theme_import.get_user_themes_root(tmp_path)

	assert root == tmp_path / "navsounds_themes"
	assert root.parent == Path(tmp_path)


def test_import_creates_the_config_path_chain(tmp_path):
	config_path = tmp_path / "portable" / "config"
	config_path.mkdir(parents=True)
	archive = make_zip(tmp_path / "Pack.zip", {"Pack/button.wav": make_wav()})

	result = theme_import.import_theme_zip(archive, config_path, NAV)

	assert result.destination == config_path / "navsounds_themes" / NAV / "Pack"
	assert result.destination.is_dir()


def test_module_stays_free_of_nvda_imports():
	source = MODULE_PATH.read_text(encoding="utf-8")

	for forbidden in ("import wx", "import config", "import addonHandler", "import ui", "from gui"):
		assert forbidden not in source


def test_translator_hook_is_applied_to_messages(tmp_path):
	original = theme_import._translator
	theme_import.set_translator(lambda text: f"[{text}]")
	try:
		with pytest.raises(theme_import.ThemeImportError) as caught:
			theme_import.import_theme_zip(tmp_path / "absent.zip", tmp_path, NAV)
	finally:
		theme_import.set_translator(original)

	assert str(caught.value).startswith("[")


def test_destination_is_never_created_when_a_conflict_cannot_be_resolved(tmp_path, monkeypatch):
	kind_dir = user_root(tmp_path) / NAV
	for name in ("Pack", "Pack (1)", "Pack (2)", "Pack (3)"):
		(kind_dir / name).mkdir(parents=True)
	archive = make_zip(tmp_path / "Pack.zip", {"Pack/button.wav": make_wav()})
	monkeypatch.setattr(theme_import, "MAX_NAME_ATTEMPTS", 2)

	with pytest.raises(theme_import.ThemeImportError):
		theme_import.import_theme_zip(archive, tmp_path, NAV)

	assert all(list((kind_dir / name).iterdir()) == [] for name in ("Pack", "Pack (1)", "Pack (2)", "Pack (3)"))
	assert stray_temp_dirs(user_root(tmp_path)) == []


def test_reimport_does_not_touch_an_already_installed_theme(tmp_path):
	first = make_zip(tmp_path / "Pack.zip", {"Pack/button.wav": make_wav(frames=8)})
	second = make_zip(tmp_path / "Pack.zip", {"Pack/button.wav": make_wav(frames=64)})

	original_result = theme_import.import_theme_zip(first, tmp_path, NAV)
	original_bytes = (original_result.destination / "button.wav").read_bytes()
	theme_import.import_theme_zip(second, tmp_path, NAV)

	assert (original_result.destination / "button.wav").read_bytes() == original_bytes
	assert (original_result.destination.parent / "Pack (1)").is_dir()


def test_no_wav_file_ever_lands_directly_in_the_themes_root(tmp_path):
	archive = make_zip(tmp_path / "Loose.zip", {"a.wav": make_wav(), "b.wav": make_wav()})

	theme_import.import_theme_zip(archive, tmp_path, NAV)

	loose = [entry.name for entry in user_root(tmp_path).iterdir() if entry.is_file()]
	assert loose == []
	assert os.listdir(user_root(tmp_path) / NAV) == ["Loose"]
