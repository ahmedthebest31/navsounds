"""Installation of user sound themes from zip archives.

Nothing in this module imports NVDA, wx, or anything from the add-on, so the
extraction engine can be exercised with the standard library alone. Callers
supply the NVDA configuration directory and decide which sound category the
theme belongs to.

The bundled packs label sounds by the directory they live in rather than by
their file name, so user themes mirror the same two level layout:

	<configPath>/navsounds_themes/navsounds/<theme>/*.wav
	<configPath>/navsounds_themes/typingsound/<theme>/*.wav
"""

import ntpath
import re
import shutil
import tempfile
import wave
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, NamedTuple

NAV_KIND = "navsounds"
TYPE_KIND = "typingsound"
THEME_KINDS = (NAV_KIND, TYPE_KIND)

USER_THEMES_DIRNAME = "navsounds_themes"
WAV_SUFFIX = ".wav"

# Bundled packs are 1 to 86 files of a few hundred kilobytes each. These limits
# leave generous headroom while keeping a malicious archive from filling the
# disk or stalling NVDA on a low end machine.
MAX_ARCHIVE_ENTRIES = 2000
MAX_TOTAL_BYTES = 64 * 1024 * 1024
COPY_CHUNK_BYTES = 64 * 1024

# Mirrors audio._SUPPORTED_SAMPLE_WIDTHS. Duplicated rather than imported so this
# module stays free of nvwave, which would drag NVDA into the tests.
SUPPORTED_SAMPLE_WIDTHS = (1, 2)

MAX_NAME_LENGTH = 64
MAX_NAME_ATTEMPTS = 999
DEFAULT_THEME_NAME = "theme"

# Files an archiver or file browser leaves behind; never worth installing.
_JUNK_NAMES = frozenset({".ds_store", "thumbs.db", "desktop.ini", ".lnk", ".gitkeep"})
_JUNK_DIRS = frozenset({"__macosx", ".git"})

# Control characters plus every character Windows forbids in a folder name.
_ILLEGAL_NAME_CHARS = re.compile(r'[\x00-\x1f<>:"/\\|?*]')
_REPEATED_SPACES = re.compile(r"\s+")


def _identity(text: str) -> str:
	return text


_translator: Callable[[str], str] = _identity


def set_translator(translator: Callable[[str], str]) -> None:
	"""Install the gettext callable used for the messages in this module."""
	global _translator
	_translator = translator


def _(text: str) -> str:
	return _translator(text)


class ThemeImportError(Exception):
	"""An archive could not be installed. The message is shown to the user."""


@dataclass(frozen=True)
class ThemeImportResult:
	"""Outcome of a successful import."""

	kind: str
	theme_name: str
	destination: Path
	file_count: int
	skipped_count: int


class _WavMember(NamedTuple):
	"""One validated wav inside an archive."""

	name: str
	stem: str
	parent: tuple[str, ...]
	info: zipfile.ZipInfo


def get_user_themes_root(config_path: str | Path) -> Path:
	"""Directory holding every user imported theme, created only on demand."""
	return Path(config_path) / USER_THEMES_DIRNAME


def list_user_themes(config_path: str | Path, kind: str) -> dict[str, Path]:
	"""Map theme name to directory for the user themes of one sound category."""
	_validate_kind(kind)
	kind_dir = get_user_themes_root(config_path) / kind
	if not kind_dir.is_dir():
		return {}
	return {entry.name: entry for entry in kind_dir.iterdir() if entry.is_dir()}


def read_archive_wav_stems(archive: str | Path) -> list[str]:
	"""Lowercased stems of every wav in the archive, for naming guesses."""
	try:
		return [member.stem for member in _scan_wavs(Path(archive))]
	except ThemeImportError:
		raise
	except OSError as error:
		raise ThemeImportError(_("the archive could not be read: {}").format(error)) from error


def import_theme_zip(
	archive: str | Path,
	config_path: str | Path,
	kind: str,
	builtin_theme_names: Iterable[str] = (),
) -> ThemeImportResult:
	"""Install a zip archive as a user theme of the given sound category.

	Extraction is atomic. Everything is unpacked into a temporary folder inside
	the user themes root, validated, and only then renamed into place, so a
	failure never leaves a half written theme behind and the final move stays on
	a single volume. builtin_theme_names keeps an import from shadowing a
	bundled theme.
	"""
	_validate_kind(kind)

	archive_path = Path(archive)
	if not archive_path.is_file():
		raise ThemeImportError(_("the selected archive does not exist"))

	members = _scan_wavs(archive_path)
	if not members:
		raise ThemeImportError(_("the archive contains no sound files"))

	root = get_user_themes_root(config_path)
	try:
		root.mkdir(parents=True, exist_ok=True)
	except OSError as error:
		raise ThemeImportError(_("the user themes folder could not be created: {}").format(error)) from error

	temp_dir = Path(tempfile.mkdtemp(prefix=".import-", dir=root))
	try:
		sounds_dir = temp_dir / "sounds"
		sounds_dir.mkdir()
		_extract(archive_path, members, sounds_dir, MAX_TOTAL_BYTES)
		usable, rejected = _keep_decodable(sounds_dir)
		if not usable:
			raise ThemeImportError(_("the archive contains no readable sound files"))

		name = _resolve_theme_name(
			_detect_theme_name(archive_path, members),
			root,
			kind,
			builtin_theme_names,
		)
		destination = root / kind / name
		destination.parent.mkdir(parents=True, exist_ok=True)

		payload = temp_dir / "payload"
		payload.mkdir()
		for source in usable:
			source.rename(payload / source.name)
		shutil.rmtree(sounds_dir, ignore_errors=True)
		payload.rename(destination)
		return ThemeImportResult(kind, name, destination, len(usable), rejected)
	except ThemeImportError:
		raise
	except OSError as error:
		raise ThemeImportError(_("the theme could not be installed: {}").format(error)) from error
	finally:
		shutil.rmtree(temp_dir, ignore_errors=True)


def _validate_kind(kind: str) -> None:
	if kind not in THEME_KINDS:
		raise ValueError(f"unknown sound theme kind: {kind!r}")


def _scan_wavs(archive_path: Path) -> list[_WavMember]:
	"""Validate every archive member and return the wavs worth extracting."""
	members: list[_WavMember] = []
	seen: set[str] = set()
	try:
		with zipfile.ZipFile(archive_path) as archive:
			infos = archive.infolist()
			if len(infos) > MAX_ARCHIVE_ENTRIES:
				raise ThemeImportError(_("the archive contains too many items"))
			for info in infos:
				if info.is_dir() or _is_junk(info.filename):
					continue
				relative = _safe_member_path(info.filename)
				if relative.suffix.lower() != WAV_SUFFIX:
					continue
				key = relative.name.casefold()
				if key in seen:
					# Names differing only in case collide both on disk and in
					# the sound cache key, so the first one wins.
					continue
				seen.add(key)
				members.append(_WavMember(relative.name, relative.stem.lower(), relative.parts[:-1], info))
	except ThemeImportError:
		raise
	except (OSError, zipfile.BadZipFile, NotImplementedError) as error:
		raise ThemeImportError(_("the archive could not be read: {}").format(error)) from error
	return members


def _is_junk(name: str) -> bool:
	"""True for OS metadata that should never reach the themes folder."""
	parts = [part for part in name.replace("\\", "/").split("/") if part]
	if not parts:
		return True
	if any(part.casefold() in _JUNK_DIRS for part in parts[:-1]):
		return True
	return parts[-1].casefold() in _JUNK_NAMES


def _safe_member_path(name: str) -> Path:
	"""Normalise an archive member name, refusing anything that escapes.

	Extraction writes only the base name, so a traversal can never reach the
	filesystem through the write. The checks below are defence in depth and also
	keep the detected wrapping folder honest.
	"""
	normalized = name.replace("\\", "/")
	if normalized.startswith("/") or ntpath.splitdrive(normalized)[0]:
		raise ThemeImportError(_("the archive contains an absolute path"))
	parts = [part for part in normalized.split("/") if part not in ("", ".")]
	if any(part == ".." for part in parts):
		raise ThemeImportError(_("the archive contains an unsafe path"))
	return Path(*parts) if parts else Path()


def _extract(archive_path: Path, members: list[_WavMember], target_dir: Path, max_bytes: int) -> None:
	"""Copy the accepted members into target_dir, refusing to exceed max_bytes."""
	total = 0
	with zipfile.ZipFile(archive_path) as archive:
		for member in members:
			with archive.open(member.info) as source, (target_dir / member.name).open("wb") as sink:
				while True:
					chunk = source.read(COPY_CHUNK_BYTES)
					if not chunk:
						break
					total += len(chunk)
					if total > max_bytes:
						raise ThemeImportError(_("the archive is too large to import"))
					sink.write(chunk)


def _keep_decodable(sounds_dir: Path) -> tuple[list[Path], int]:
	"""Split the extracted files into loadable ones and the rest.

	One unreadable file must not cost the user a whole theme, so bad files are
	dropped individually and only an entirely unreadable archive fails.
	"""
	usable: list[Path] = []
	rejected = 0
	for path in sorted(sounds_dir.iterdir()):
		if _is_decodable(path):
			usable.append(path)
			continue
		path.unlink(missing_ok=True)
		rejected += 1
	return usable, rejected


def _is_decodable(path: Path) -> bool:
	"""Apply the same limits as the audio engine so no dead file is installed."""
	try:
		with wave.open(str(path), "rb") as reader:
			return (
				reader.getnframes() > 0
				and reader.getnchannels() > 0
				and reader.getsampwidth() in SUPPORTED_SAMPLE_WIDTHS
			)
	except (OSError, EOFError, wave.Error):
		return False


def _detect_theme_name(archive_path: Path, members: list[_WavMember]) -> str:
	"""Name the theme after the directory that actually holds the audio.

	Archives are routinely wrapped in release folders, for example
	"empty_folder/release/build/Pack/button.wav". The deepest directory shared
	by every wav is the real theme root, so the superfluous parents are skipped
	instead of leaking into the installed name. Files sitting directly at the
	archive root share no parent at all, so the archive name is used then.
	"""
	common = _shared_prefix([member.parent for member in members])
	if common:
		sanitized = _sanitize_theme_name(common[-1])
		if sanitized:
			return sanitized
	return _sanitize_theme_name(archive_path.stem) or DEFAULT_THEME_NAME


def _shared_prefix(parents: list[tuple[str, ...]]) -> tuple[str, ...]:
	"""Longest directory prefix shared by every given path."""
	if not parents:
		return ()
	shared = parents[0]
	for parent in parents[1:]:
		shared = tuple(first for first, second in zip(shared, parent, strict=False) if first == second)
		if not shared:
			break
	return shared


def _sanitize_theme_name(raw: str) -> str:
	"""Make a folder name that Windows accepts while keeping spaces intact."""
	name = _REPEATED_SPACES.sub(" ", _ILLEGAL_NAME_CHARS.sub(" ", raw)).strip(" .")
	return name[:MAX_NAME_LENGTH].strip(" .")


def _resolve_theme_name(base: str, root: Path, kind: str, builtin_theme_names: Iterable[str]) -> str:
	"""Pick a folder name that collides with neither a user nor a bundled theme."""
	taken = {name.casefold() for name in builtin_theme_names}
	kind_dir = root / kind
	if kind_dir.is_dir():
		taken.update(entry.name.casefold() for entry in kind_dir.iterdir())
	for index in range(MAX_NAME_ATTEMPTS + 1):
		candidate = base if index == 0 else f"{base} ({index})"
		if candidate.casefold() not in taken:
			return candidate
	raise ThemeImportError(_("no free name was found for the imported theme"))
