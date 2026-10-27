# Navigation Sounds

[![CI](https://github.com/ahmedthebest31/navsounds/actions/workflows/build_addon.yml/badge.svg)](https://github.com/ahmedthebest31/navsounds/actions/workflows/build_addon.yml)
[![License: GPL v2](https://img.shields.io/badge/License-GPL%20v2-blue.svg)](https://www.gnu.org/licenses/old-licenses/gpl-2.0.html)
[![NVDA Compatibility](https://img.shields.io/badge/NVDA-2019.3%2B-brightgreen.svg)](https://www.nvaccess.org/download/)

NVDA add-on that plays sounds when you move between elements and when you type. Different roles and states get different sounds, and you can swap the whole sound set.

## Features

- Play a sound for the role and state of the element you land on (buttons, links, headings, checkboxes, and so on).
- Play typing sounds while you type, with several keyboard sound packs.
- Toggle object sounds and typing sounds with NVDA+alt+n.
- Settings page under NVDA menu, Preferences, Settings, Navigation Sounds: pick a pack, set volume, toggle mouse hover and arrow-key sounds.
- Import your own sound packs from a .zip file.
- Browse and download community packs from the sound store.
- Runs on NVDA 2019.3 and newer on Windows.
- Translated into English, Arabic, Italian, French, Spanish, Portuguese, Polish, Ukrainian, Vietnamese and Simplified Chinese.

## Installation

### Direct Installation (NVDA Version 2023.2+)

For users on NVDA 2023.2 or newer:
- Navigate to the Add-on store.
- Search for "Navigation Sound Effects" and install.

### Manual Installation (For Older Versions)

1. Visit the [Releases](https://github.com/ahmedthebest31/navsounds/releases/) section and download the latest release.
2. Open the downloaded add-on file and confirm the installation with "OK".
3. NVDA will restart automatically. Enjoy the enhanced audio feedback with Navigation Sounds!


## Sound Store

**[Open the sound store](https://ahmedthebest31.github.io/navsounds/store/)**

The store is a simple page that lists downloadable sound packs. Every pack shows
its name, a description, who made it, an audio preview you can play right on the
page, and a download link. You can filter the list down to navigation sounds only,
typing sounds only, or show everything.

Packs come from two places:

- **Bundled with the add-on**: the sound effects that ship with Navigation Sounds.
- **Submitted by the community**: anyone can send a pack in, see below.

### Installing a pack from the store

1. Install the add-on first, using the steps above.
2. Download the pack you want from the store. You get a single `.zip` file.
3. Open `NVDA menu > Preferences > Settings > Navigation Sounds`.
4. Press **import sound theme...**, pick the downloaded `.zip`, and confirm the
   kind of pack you are importing.
5. Choose the new pack in the **select sound** or **select typing sound** list,
   then save.

### Your own packs survive add-on updates

Imported packs are installed into your own NVDA configuration directory, inside
`navsounds_themes`. The add-on never modifies or deletes that folder, and never
overwrites a pack that already ships with the add-on. Updating Navigation Sounds
therefore leaves your imported packs untouched, and they stay selected. If you
later install a newer version of a pack you imported yourself, it is added
alongside the older copy rather than replacing it, so you can always go back.

The only thing an update can change is the list of packs that come with the
add-on itself. If a bundled pack is ever renamed or removed in a future version,
an imported copy of the same name under a different folder name keeps working.

### Submitting a pack

Packs are contributed through GitHub issues, so no account or upload tooling
beyond a GitHub login is needed:

1. Open
   [a new sound pack issue](https://github.com/ahmedthebest31/navsounds/issues/new?template=sound_theme_submission.yml).
2. Fill in the pack name, a short description, and which kind it is.
3. Drag your `.zip` file into the archive field, and optionally a single sound
   file to use as the store preview.
4. Confirm you tested the pack on your own machine, and give your NVDA version
   and add-on version.
5. Tick that you have the right to share the sound files.

If you want the store to show a name other than your GitHub account name, fill in
the credit field with the name you want printed on the pack card.

Once the pack is reviewed and tested it is added to the store, and you are
credited on its card.


## Contributing

Contributions are welcome! Whether you've found a bug, have an improvement idea, or want to contribute in any other way, check out our [Contributing Guide](./CONTRIBUTING.md) for details on how to get started.

## License

This project is licensed under the [GNU General Public License, version 2](LICENSE).