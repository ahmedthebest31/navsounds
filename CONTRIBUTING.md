# Contributing to navSounds

Thank you for helping improve navSounds. This guide covers development setup, the sound pack format, and how to send changes.

## Development setup

1. Windows with Python 3.11 or newer.
2. Install uv (https://docs.astral.sh/uv/).
3. Sync project tooling:

```
uv sync
```

4. Common commands:

- Lint: `uv run ruff check navsounds tests`
- Format: `uv run ruff format navsounds tests`
- Tests: `uv run pytest tests`

Continuous Integration runs lint, format check, tests, and an add-on build on every push to main and on pull requests. Please keep all of them green; pull requests cannot be merged while required checks fail.

## Sound pack format

Sound packs live under:

```
navsounds/globalPlugins/NavigationSounds/effects/<scheme>/<category>/
```

Each scheme has two categories:

1. `navsounds` - navigation sounds.
2. `typingsound` - typing sounds.

Navigation files are named after NVDA roles:

- Pattern: `nav_<role>.wav`
- `<role>` is the controlTypes.Role name, lowercased, without underscores.
- Examples: `button.wav` becomes `nav_button.wav`; role HEADING1 becomes `nav_heading1.wav`.
- Roles with no matching file simply stay silent, so packs can cover only the roles they care about.
- Heading levels are already supported this way: adding `heading1.wav` through `heading6.wav` gives each level its own sound.

Typing sounds use the prefix `type_`; they are played randomly while typing.

All WAV files are decoded and converted at load time to stereo, 16-bit, 48000 Hz PCM, so any standard WAV works as a source regardless of its original rate or channel count. Keep clips short (a few hundred milliseconds) for the best experience.

## Sending changes

1. Open an issue first for large features or behavior changes.
2. Create a focused branch per change.
3. Run lint, format, and tests locally before pushing.
4. Write commit messages in English using Conventional Commits style.

## Reporting bugs

Please include:

1. NVDA version and Windows version.
2. Exact steps to reproduce.
3. Whether the problem disappears when the add-on is disabled.
