"""Tests for the sound store page and the submission form that feeds it.

The page is plain HTML with its CSS and JS inline, so it is read here as text.
What is checked is the contract the rest of the project depends on: the add-on's
store link resolves to a page that exists in this repository, every download and
every preview on the page exists on disk, every pack archive still imports
through the real importer, and the submission form asks for everything needed to
add a pack.
"""

import re
import shutil
import subprocess
import wave
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from test_theme_import import theme_import
from test_theme_store_ui import load_settings_module

REPO_ROOT = Path(__file__).resolve().parents[1]
STORE_DIR = REPO_ROOT / "store"
PAGE = STORE_DIR / "index.html"
FORM = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "sound_theme_submission.yml"

CATEGORY_KINDS = {
	"navigation": theme_import.NAV_KIND,
	"typing": theme_import.TYPE_KIND,
}

PACK_CARD = re.compile(r'<article class="pack" data-category="([^"]+)">(.*?)</article>', re.DOTALL)


def page() -> str:
	assert PAGE.is_file(), "the store page is missing from the repository"
	return PAGE.read_text(encoding="utf-8")


def form() -> str:
	assert FORM.is_file(), "the submission form is missing from the repository"
	return FORM.read_text(encoding="utf-8")


def search(pattern: str, text: str, what: str) -> re.Match:
	match = re.search(pattern, text, re.DOTALL)
	assert match is not None, f"could not find {what}"
	return match


def cards() -> list[dict]:
	"""Every pack card on the page, with the parts the layout depends on."""
	found = []
	for category, body in PACK_CARD.findall(page()):
		found.append(
			{
				"category": category,
				"name": search(r"<h3>(.*?)</h3>", body, "a pack name").group(1).strip(),
				"description": search(r"<p>(.*?)</p>", body, "a pack description").group(1).strip(),
				"author": search(r'<p class="pack-author">(.*?)</p>', body, "a pack author").group(1).strip(),
				"sample": search(r"<audio\b[^>]*\bsrc=\"([^\"]+)\"", body, "a preview file").group(1),
				"archive": search(r'<a class="button"[^>]*\bhref="([^"]+)"', body, "a download link").group(1),
			}
		)
	return found


def card_names() -> list[str]:
	return [card["name"] for card in cards()]


def test_the_store_link_resolves_to_the_page_in_this_repository(monkeypatch):
	"""The add-on opens STORE_URL in a browser, so it has to match where the
	page actually is. The published host is not asserted, only the path."""
	_, settings_module = load_settings_module(monkeypatch)
	path = urlsplit(settings_module.STORE_URL).path
	assert path.endswith("/store/"), f"the store link points at {path}, not at the store folder"
	assert PAGE.is_file()


def test_the_page_loads_nothing_from_the_network():
	"""An add-on audience runs this page on slow connections and offline."""
	source = page()
	for forbidden in ('src="http', "src='http", "@import", "fonts.googleapis", "cdn.", "<link "):
		assert forbidden not in source, f"the page references {forbidden}"
	for url in re.finditer(r"https?://[^\s\"'<>]+", source):
		assert source[url.start() - 6 : url.start()] == 'href="', (
			f"{url.group()} is fetched by the page instead of being a plain link"
		)


def test_the_page_has_one_first_level_heading():
	assert page().count("<h1") == 1


def test_every_pack_card_carries_name_description_author_player_and_download():
	found = cards()
	assert found, "the store lists no packs"
	for card in found:
		assert card["name"], "a pack has no name"
		assert card["description"], f"{card['name']} has no description"
		assert card["author"], f"{card['name']} has no author"
		assert card["sample"], f"{card['name']} has no preview"
		assert card["archive"].endswith(".zip"), f"{card['name']} does not download a zip"


def test_every_pack_sits_next_to_the_page_in_the_store_folder():
	for card in cards():
		for key in ("sample", "archive"):
			relative = card[key]
			assert not relative.startswith(("/", "http")), f"{card['name']} links outside the store"
			assert relative.startswith("packs/"), f"{card['name']} is not filed under store/packs"


def test_every_file_the_page_points_at_exists():
	for card in cards():
		for key in ("sample", "archive"):
			target = STORE_DIR / card[key]
			assert target.is_file(), f"{card['name']} links to {card[key]}, which does not exist"


def test_every_filter_choice_is_offered():
	source = page()
	assert 'name="pack-filter"' in source
	for value in ("all", *CATEGORY_KINDS):
		assert f'value="{value}"' in source, f"the filter has no {value} choice"
	for category in CATEGORY_KINDS:
		assert category in [card["category"] for card in cards()], f"no pack uses the {category} category"


def test_every_preview_is_a_playable_wav_of_a_judgeable_length():
	"""The preview has to decode in a browser and be long enough to form an
	opinion about the pack. It is allowed to be a longer excerpt rather than a
	verbatim file from the archive, so this checks decodability and length
	instead of byte equality."""
	for card in cards():
		preview = STORE_DIR / card["sample"]
		try:
			with wave.open(str(preview), "rb") as sound:
				seconds = sound.getnframes() / sound.getframerate()
				depth = sound.getsampwidth() * 8
		except (wave.Error, EOFError) as error:
			pytest.fail(f"the preview for {card['name']} is not a playable wav: {error}")
		assert depth in (16, 32), f"the preview for {card['name']} is {depth} bit, which browsers may refuse"
		assert 0.2 <= seconds <= 30, f"the preview for {card['name']} runs {seconds:.2f} seconds"


def test_no_store_asset_is_ignored_by_git():
	"""The repository ignores *.zip for build artifacts, and that rule silently
	dropped both downloadable packs before it was narrowed. Nothing else in the
	page or the importer would have noticed."""
	if shutil.which("git") is None:
		pytest.skip("git is not available on this machine")
	for card in cards():
		for key in ("sample", "archive"):
			asset = STORE_DIR / card[key]
			ignored = subprocess.run(
				["git", "check-ignore", "--no-index", "--quiet", str(asset)],
				cwd=REPO_ROOT,
				shell=False,
			).returncode
			assert ignored == 1, f"{asset.relative_to(REPO_ROOT)} is ignored, so it would never reach GitHub"


@pytest.mark.parametrize("category", sorted(CATEGORY_KINDS))
def test_every_store_archive_still_imports(category, tmp_path):
	"""The store hands out archives the importer has to accept."""
	for card in cards():
		if card["category"] != category:
			continue
		with zipfile.ZipFile(STORE_DIR / card["archive"]) as archive:
			expected = [name for name in archive.namelist() if name.lower().endswith(".wav")]
		result = theme_import.import_theme_zip(
			STORE_DIR / card["archive"], tmp_path / "config", CATEGORY_KINDS[category]
		)
		assert result.kind == CATEGORY_KINDS[category]
		assert result.theme_name == Path(card["archive"]).stem, (
			f"{card['name']} would import as {result.theme_name}, not as its store name"
		)
		assert result.file_count == len(expected)
		assert result.skipped_count == 0, f"{card['name']} has a file the importer cannot read"


def test_the_store_folder_is_not_inside_the_packaged_addon():
	"""The release workflow zips the navsounds folder only, so anything inside
	it would ship inside the add-on as well."""
	assert not (REPO_ROOT / "navsounds" / "store").exists()
	assert STORE_DIR.parent == REPO_ROOT


def test_the_submission_form_asks_for_a_name_a_description_and_a_zip():
	source = form()
	assert "name: Sound theme submission" in source
	assert "title:" in source
	for field in ("pack-name", "description", "archive"):
		assert f"id: {field}" in source, f"the form has no {field} field"


def test_the_submission_form_asks_for_a_preview_sample():
	source = form()
	assert "id: sample" in source
	assert "preview" in search(r"id: sample(.*?)\n  - type:", source, "the sample field").group(1)


def test_the_submission_form_asks_for_tested_versions():
	source = form()
	assert "id: nvda-version" in source
	assert "id: addon-version" in source
	confirmations = search(r"id: confirmations(.*)", source, "the confirmations block").group(1)
	assert "tested" in confirmations.lower()
	assert confirmations.count("required: true") >= 3, "the form must require the test and rights confirmations"


def test_the_submission_form_allows_a_display_name():
	source = form()
	credit = search(r"id: credit-name(.*?)\n  - type:", source, "the credit field").group(1)
	assert "GitHub account" in credit
