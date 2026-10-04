# Sound store

`index.html` is the sound store page. The add-on opens it from the
**open theme store** button, so `STORE_URL` in
`navsounds/globalPlugins/NavigationSounds/settings.py` must match the path this
folder is published at.

Everything is deliberately self-contained: no CDN, no web font, no build step, no
JavaScript dependency. The page renders and the packs stay downloadable with
scripts blocked, and `tests/test_store_page.py` fails if an external reference is
ever added.

## Layout

```
store/
  index.html                    the page, with its CSS and JS inline
  packs/
    <slug>/
      <slug>.zip                what the download link points at
      sample.wav                the preview played on the page
```

The pack folder name is the slug, and the zip inside it must have the same name.
The importer takes the theme name from the deepest folder shared by the wav
files, so a flat archive falls back to the archive name. Keeping the two equal
means the store name, the file name, and the imported theme name all agree.

`sample.wav` should be a genuine recording of the pack, but it does not have to be
a byte-for-byte copy of one file inside the zip: a longer excerpt that shows the
pack off is allowed. It does have to be a 16 or 32 bit PCM wav between 0.2 and 30
seconds, because the tests decode it and browsers refuse anything they cannot
play.

## Adding a pack

1. Put the archive and the sample in `store/packs/<slug>/`. The repository
   ignores `*.zip` for build artifacts, so `.gitignore` carries a negation for
   `store/packs/`; `tests/test_store_page.py` fails if that rule ever stops
   working, because an ignored zip still renders on the page but never reaches
   GitHub.
2. Add an `article.pack` to `index.html` with `data-category` set to
   `navigation` or `typing`, an `h3`, a description, an author, an `audio`
   element pointing at the sample, and a download link pointing at the zip.
3. Run `uv run pytest tests/test_store_page.py`. It checks that every link and
   sample in the page exists on disk and that every zip still imports.

Keep the card order in the same shape every time: name, description, author,
player, download.

## What a good archive looks like

- wav files only, inside one folder or at the top level. Nested folders are
  flattened on import, so there is no need to arrange them.
- 16 bit PCM mono at the rate NVDA plays at. `audio.py` rejects anything it
  cannot decode, and the importer silently drops a file it cannot read, so a
  broken file means a pack that is quietly missing one sound.
- One file per sound, named after the role it plays, so the kind of the pack can
  be detected: navigation packs name files after `controlTypes` roles such as
  `button.wav` or `link.wav`, typing packs do not.
- The archive is capped at 2000 entries and 64 MiB by the importer.