from gettext import GNUTranslations
from pathlib import Path


ADDON_ROOT = Path(__file__).resolve().parents[1] / "navsounds"


def test_simplified_chinese_resources_use_nvda_locale_identifier():
	locale_dir = ADDON_ROOT / "locale" / "zh_CN"

	assert not (ADDON_ROOT / "locale" / "zh-cn").exists()
	assert (locale_dir / "manifest.ini").is_file()
	assert (ADDON_ROOT / "doc" / "zh_CN" / "readme.html").is_file()


def test_simplified_chinese_catalog_contains_current_settings_labels():
	mo_path = ADDON_ROOT / "locale" / "zh_CN" / "LC_MESSAGES" / "nvda.mo"
	with mo_path.open("rb") as mo_file:
		translations = GNUTranslations(mo_file)

	assert translations.gettext("say element roles") == "读出元素角色"
	assert translations.gettext("say element states") == "读出元素状态"
