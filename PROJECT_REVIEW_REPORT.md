# NavSounds Project Review Report

Date: 2026-07-24

---

## 1. Project Overview

**Repository:** github.com/ahmedthebest31/navsounds
**Description:** NVDA screen reader add-on providing navigation and typing sound effects with customizable sound packs, browse mode support, and mouse hover feedback.
**License:** GNU General Public License v2
**Current Version:** 2.0.1 (manifest.ini) / 2.1.0 (CHANGELOG.md)

---

## 2. Project Status

### 2.1 Architecture
The project follows the standard NVDA add-on structure:
- `navsounds/manifest.ini` - Manifest file
- `navsounds/globalPlugins/NavigationSounds/__init__.py` - Main plugin (GlobalPlugin)
- `navsounds/globalPlugins/NavigationSounds/browser.py` - Browse mode interception
- `navsounds/globalPlugins/NavigationSounds/audio.py` - Audio engine (MultiPlayerManager)
- `navsounds/globalPlugins/NavigationSounds/settings.py` - Settings panel (wx)
- `navsounds/locale/` - Translations
- `navsounds/effects/` - Sound packs
- `navsounds/doc/` - Documentation
- `.github/workflows/build_addon.yml` - CI/CD

### 2.2 What Works Well
- Standard NVDA add-on structure followed correctly
- Multi-language support (English, Arabic, Italian, French, Spanish, Portuguese, Polish, Danish, Ukrainian, Chinese simplified)
- Good feature set: nav sounds, typing sounds, mouse hover sounds, sound pack selection
- Community engagement with translation PRs merged regularly
- GitHub Actions workflow for automated builds and releases

---

## 3. Critical Issues Found

### 3.1 CRITICAL: Browse Mode Navigation Broken on NVDA 2025.1+

**Status:** Issue #37 closed, Issue #41 still OPEN (10 comments, unresolved)
**Impact:** Users on NVDA 2025.1+ report navigation sounds do NOT play when using arrow keys or quick navigation (h, k, b, etc.) in browse mode. Tab/Shift+Tab works.

**Root Cause (from Issue #37):**
NVDA PR #17598 removed the "Automatically set system focus to focusable elements" setting. The current code relied on `event_gainFocus` to detect browse-mode element changes, but system focus no longer follows the browse-mode cursor in NVDA 2025.1+.

**Current main branch approach:**
- Registers a handler on `vision.visionHandlerExtensionPoints.post_browseModeMove` (correct approach)
- Falls back to monkey-patching `_quickNavScript` and `_caretMovementScriptHelper` on older NVDA versions
- The `post_browseModeMove` approach IS the correct one per NVDA team recommendation

**Problem on main:** The `_post_browseModeMove_handler` in `__init__.py` only plays the Role sound, it does NOT check States first (unlike `event_gainFocus` which does). This means for elements with special states (e.g. pressed, focused), the wrong sound might play.

### 3.2 CRITICAL: Speech Monkey-Patch Fragility

**Status:** Issue #41 reports "speech output stops working" on latest NVDA
**Impact:** Complete speech breakage for users

**Root Cause:** The code monkey-patches `speech.speech.getPropertiesSpeech` directly. In NVDA 2026+, the module layout changed (speech module may be nested differently). The current main code uses `speech.speech.getPropertiesSpeech` which may not exist in newer NVDA versions.

**Fix needed:** Try both `speech.getPropertiesSpeech` and `speech.speech.getPropertiesSpeech` with proper fallback.

### 3.3 CRITICAL: Version Mismatch

`manifest.ini` says version `2.0.1` but CHANGELOG.md describes version `2.1.0` features. The manifest needs updating.

### 3.4 HIGH: lastTestedNVDAVersion is Outdated

`lastTestedNVDAVersion = 2026.1` but Issue #41 reports problems on "latest version" (2026.2+). Should be updated to `2026.2` or the latest tested version after fixes.

---

## 4. Open PR Analysis

### PR #38: Fix browse mode navigation sounds via NVDA extension point (OPEN)

**Author:** aim9sour
**Branch:** fix/browse-mode-navigation-sounds
**Status:** Open, 9 comments, last updated 2026-07-22
**Files changed:** 4 files (+94, -131 lines net)
**Tests:** Adds 2 test files (330 lines total), all 10 tests pass

**What it does:**
1. Replaces the inline `_post_browseModeMove_handler` with a new `BrowseModeMoveListener` class in `browser.py`
2. Uses `vision.visionHandlerExtensionPoints.post_browseModeMove` as the primary mechanism
3. Falls back to `BrowseModeQuickNavInterceptor` (monkey-patching) when the extension point is unavailable
4. Centralizes role/state sound dispatch into `_play_nav_for_object()` used by focus, mouse, and browse-mode
5. Fixes speech monkey-patch to work with both modern (`speech.getPropertiesSpeech`) and legacy (`speech.speech.getPropertiesSpeech`) layouts
6. Properly syncs browse listener on settings change (settings.py patch)
7. Fixes `_mouse_timer` cleanup (sets to None after Stop)
8. Adds `hasattr` safety checks in `get_property2_speech` and `terminate`

**Quality Assessment:**
- Code quality: HIGH - well structured, clean separation of concerns
- Tests: Good unit test coverage for BrowseModeMoveListener
- Backward compatibility: Excellent - handles multiple NVDA versions
- Error handling: Good - logs errors only once, swallows exceptions in handlers
- The PR directly addresses Issue #37 and partially addresses Issue #41

**Recommendation:** MERGE this PR. It is the correct fix for the browse-mode navigation sound breakage on NVDA 2025.1+.

---

## 5. Issues Analysis

### Open Issues

| # | Title | Recommendation |
|---|-------|----------------|
| 41 | Add-on causes speech output to break on latest NVDA | HIGH PRIORITY - Needs investigation. PR #38 partially fixes this via the speech module fallback. After merging PR #38, retest. |
| 45 | New idea: heading level audio navigation (h1-h6) | GOOD FEATURE REQUEST - Implement per-heading-level sounds. The code already handles Role.HEADING in the role sound mapping. |

### Closed Issues (recent, notable)

| # | Title | Notes |
|---|-------|-------|
| 43 | Vietnamese translation update | Merged via PR #44 |
| 40 | Talkback sound error | Fixed and closed |
| 37 | Browse mode navigation broken on NVDA 2025.1+ | Closed, but fix is in PR #38 (not yet merged) |
| 35 | Audio contributions (typing sounds) | Acknowledged, closed |

---

## 6. Closed PRs Analysis

All closed PRs have been properly merged. Notable:
- PR #24 (Smaller files - .ogg conversion) - Merged, added base.dll for OGG playback
- PR #22 (Browser quick navigation) - Merged, added browse mode interception
- PR #20 (Fast version - performance) - Merged, added caching and multi-player manager
- PR #19 (NVDA 2026 compatibility) - Merged, updated controlTypes usage
- PR #44 (Vietnamese translation update) - Merged

---

## 7. Code Quality Issues

### 7.1 DRY Violations
The state-first-then-role sound dispatch logic is duplicated 3 times in main:
- `event_gainFocus`
- `_play_mouse_sound_delayed`
- `_post_browseModeMove_handler`

PR #38 fixes this by centralizing into `_play_nav_for_object()`.

### 7.2 Missing `__all__` exports
No `__all__` defined in `__init__.py`, which is fine for NVDA addons but could be cleaner.

### 7.3 No Type Stubs or py.typed
No type checking configuration. The code uses type hints well but has no mypy/pyright config.

### 7.4 Test Coverage
- PR #38 adds tests but only for `browser.py` and the `_play_nav_for_object` method
- No tests for `audio.py`, `settings.py`, or the speech monkey-patch logic
- Consider adding tests for the audio engine and settings panel

### 7.5 Import Structure
Main `__init__.py` imports `BrowseModeQuickNavInterceptor` but after PR #38, it will import `BrowseModeMoveListener`. The current main code still uses the old import.

---

## 8. Manifest.ini Compliance (per NVDA Developer Guide)

**Current manifest.ini:**
```ini
name = navSounds
summary = Navigation Sound Effects
version = 2.0.1
changelog = ...
author = Ahmed Samy
url = https://github.com/ahmedthebest31/navsounds/
docFileName = readme.html
minimumNVDAVersion = 2019.3
lastTestedNVDAVersion = 2026.1
updateChannel = None
```

**Issues:**
1. `version` should be `"2.0.1"` (with quotes per NVDA manifest format, though unquoted works)
2. `version = 2.0.1` mismatches CHANGELOG `2.1.0`
3. `description` field is present in the manifest file content but listed as `changelog` key with multiline - verify this renders correctly in NVDA addon store
4. `lastTestedNVDAVersion = 2026.1` needs updating to current tested version
5. `minimumNVDAVersion = 2019.3` - This is reasonable given the code uses `controlTypes.Role` and `controlTypes.State` enums which were added in NVDA 2019.2+

---

## 9. GitHub Actions Assessment

**Current workflow:** `.github/workflows/build_addon.yml`

```yaml
- Trigger: push to main, tags v*, PRs to main, manual dispatch
- Build: zip navsounds/ folder into .nvda-addon
- Upload artifact
- Create GitHub Release on tag push
```

**Assessment:**
- Basic but functional
- Missing: No linting step (ruff, flake8, or mypy)
- Missing: No test execution step (pytest should run before build)
- Missing: No addon manifest validation
- Recommendation: Add a lint/test step before packaging

---

## 10. README.md Assessment

**Current README:**
- Good feature overview
- Installation instructions for both modern and older NVDA
- Contributing section
- Missing: Screenshots or demo
- Missing: NVDA version compatibility matrix
- Missing: Troubleshooting section
- Missing: Link to CHANGELOG from README body
- Missing: Badges (build status, NVDA addon store version, license)

**Recommendation:** Add build status badge and NVDA addon store badge.

---

## 11. Recommendations Summary

### Immediate (High Priority)
1. **Merge PR #38** - This is the critical fix for browse-mode navigation on NVDA 2025.1+
2. **Update manifest.ini version** to match CHANGELOG (2.1.0)
3. **Update lastTestedNVDAVersion** to 2026.2 after testing
4. **Investigate Issue #41** - speech breakage on latest NVDA (PR #38's speech fallback should help)

### Short Term
5. **Add pytest to CI workflow** - run tests before building
6. **Add linting to CI** (ruff or flake8)
7. **Implement Issue #45** - heading level sounds (h1-h6 differentiation)
8. **Update README** with badges and troubleshooting

### Medium Term
9. **Add more tests** for audio.py and settings.py
10. **Consider manifest.json** format (NVDA 2024.1+ supports it alongside manifest.ini)
11. **Add pyproject.toml** for development tooling (ruff, mypy, pytest config)

---

## 12. NVDA Add-on Template Comparison

Based on analysis of the official NVDA add-on template (github.com/nvaccess/addonTemplate), here is a comparison of what we follow, what we don't, and what we can benefit from.

### 12.1 What We Follow (Good)

- **Basic folder structure:** `globalPlugins/`, `locale/`, `effects/`, `doc/` — correct
- **manifest.ini:** Present with all required fields (name, summary, description, version, changelog, author, url, docFileName, minimumNVDAVersion, lastTestedNVDAVersion, updateChannel) — correct
- **License:** GPL v2 — correct
- **Translations:** gettext-based `.po`/`.mo` files — correct
- **GitHub Actions:** Basic build and release workflow — functional but basic

### 12.2 What the Template Has That We Don't

| Feature | Template | NavSounds | Benefit |
|---------|----------|-----------|---------|
| `buildVars.py` | Centralized addon metadata with translatable strings | manifest.ini written manually | Template approach makes metadata reusable and translatable |
| `sconstruct` | Full SCons build system with validation, pot generation, md-to-html conversion, manifest templating | Simple `zip -r` in CI | SCons validates version numbers, compiles .po to .mo, converts docs, and generates manifest from template |
| `manifest.ini.tpl` | Template with placeholders filled from buildVars | Hardcoded manifest.ini | Allows dynamic version injection during build |
| `manifest-translated.ini.tpl` | Auto-generates localized manifests from .po files | No manifest translation | Users see manifest in their language |
| `pyproject.toml` | Full dev tooling config (ruff, pyright, pytest) | No dev tooling config | Enforces code quality |
| `prek.toml` | Git hooks for linting, formatting, type checking on every commit | No pre-commit hooks | Prevents bad code from being committed |
| `dependabot.yml` | Auto-updates GitHub Actions dependencies weekly | No dependabot | Keeps Actions secure and up-to-date |
| `crowdinL10n.yml` | Automated Crowdin translation sync | No automated translation workflow | Manages translations at scale |
| `style.css` | Styled HTML documentation | No CSS for docs | Better-looking addon store pages |
| `.python-version` | Pins Python version for reproducibility | No Python version pinning | Consistent builds |
| `.vscode/` | VS Code integration with NVDA autocompletion | No IDE config | Better developer experience |
| Tests in CI | `uv run prek run --all-files` runs lint+format+typecheck | No tests in CI | Quality gate before merge |

### 12.3 What We Can Adopt (Recommended)

**Priority 1 - Immediately useful:**

1. **Upgrade CI workflow** — Replace simple `zip` with SCons build, or at minimum add pytest and ruff steps to existing workflow
2. **Add `pyproject.toml`** — Configure ruff (linting) and pyright (type checking) for code quality
3. **Add `dependabot.yml`** — One file, keeps GitHub Actions dependencies updated automatically
4. **Add pre-commit hooks** — Even a simple `.pre-commit-config.yaml` with ruff would catch issues before commit

**Priority 2 - Medium effort, high value:**

5. **Adopt SCons build system** — Validates version numbers, compiles translations, generates localized manifests, converts markdown docs to HTML
6. **Use `buildVars.py`** pattern — Centralize addon metadata for reuse in builds and translations
7. **Add `style.css`** — Improve documentation appearance on NVDA addon store

**Priority 3 - Nice to have:**

8. **Crowdin integration** — Automate translation management if the project scales
9. **VS Code config** — If you use VS Code for development
10. **`.python-version`** — Pin Python for reproducible builds

### 12.4 Key Differences in Build Approach

**Our approach (current):**
```yaml
# Simple zip-based build
- run: cd navsounds && zip -r ../navSounds-${{ github.ref_name }}.nvda-addon ./*
```

**Template approach (recommended):**
```yaml
# Full build pipeline
- run: uv run scons && uv run scons pot
# This does: version validation, .po->.mo compilation, manifest generation,
#             markdown->html conversion, .nvda-addon packaging
```

The template approach is more robust because it:
- Validates version numbers (must be major.minor.patch integers)
- Compiles translations automatically
- Generates localized manifest files
- Converts markdown documentation to HTML
- Produces a `.pot` template file automatically

### 12.5 Summary

**NavSounds is a well-structured, functional NVDA add-on.** The core code quality is good, the features work well, and the basic structure follows NVDA conventions. The main gaps are in **development tooling** and **build infrastructure**, not in the add-on code itself. Adopting even a few items from the template (especially pyproject.toml, dependabot.yml, and an improved CI workflow) would significantly improve code quality and maintenance.

---

*Report generated by code review analysis — Updated 2026-07-24*
