*English · [Bahasa Indonesia](README-ID.md)*

# musicbox

A TUI music player for Linux. Local library, YouTube search and downloads,
queue, albums, visualizer, and real cover art in the terminal.

Colours follow the [Caelestia Shell](https://github.com/caelestia-dots/shell)
scheme when it is available, and fall back to a built-in palette when it is not.

```
┌ Library │ Search │ Queue │ Albums │ Liked │ Radio │ Downloads ─┬──────────┐
│                                                                │ [cover]  │
│  Title                          Artist       Duration          │          │
│  ...                                                           │ ▶ play   │
│                                                                │ ＋ queue │
│                                                                │ ♪ album  │
├────────────────────────────────────────────────────────────────┴──────────┤
│  ▁▂▄▆█▆▄▂▁  ▂▄▆█▇▅▃▁  (cava)                                              │
├───────────────────────────────────────────────────────────────────────────┤
│  ▶ Song title    ⏮ ⏸ ⏭ ⏹ ⇄ ↻auto ◫cava 📻radio ♪lyrics  🕪 ▬▬▬     3:35 │
└───────────────────────────────────────────────────────────────────────────┘
```

## Features

- **Library** from `~/Music`, tags read with mutagen and cached so later starts
  are instant.
- **Search and play from YouTube**, with radio that follows recommendations.
- **Downloads** to `~/Music` as mp3 or opus, with cover art and metadata
  embedded. Progress shows a pacman-style bar with size, speed, and ETA, and
  finished songs land in the Library without a manual rescan.
- **Queue** you can reorder, and **albums** stored as a tree.
- **Visualizer** reading cava's raw output.
- **Real cover art** over sixel, not ASCII blocks.
- **Now-playing markers** across the library, queue, and album lists.
- **Resume** — the song and position come back when you reopen the app.
- **Full player page** (`L`) — large cover, title, and synced lyrics that scroll
  with the song. Songs with lyrics available are marked ♪ in the Library.
- **Readable search results** — view counts in the table, like counts in the
  side panel, sort by most viewed (`o`), and load more results (`m`). Songs you
  already have are marked `⭳`.
- **Survives a crash**: if mpv dies, musicbox brings it back at the same song
  and the same second instead of freezing silently.
- **Built-in MPRIS** — musicbox registers itself on D-Bus, so it appears in
  desktop media widgets with title, cover art, and controls, without leaning on
  an mpv plugin that can take the player down with it. Artist and title are sent
  in cleaned-up form so widgets that look up lyrics themselves can find them.
- **Radio panel** — what plays next while radio is on, with an indicator in the
  control bar you can click to jump there.
- **Liked songs** (`l`) and **recommendations** (`V`) built from the YouTube
  Mixes of those songs.
- **Two languages** — English by default, Indonesian via `g` or Settings.
- **Grouped settings** (`,`) — appearance, language, playback, controls, about.
  `?` opens the same overlay straight at the shortcut list, which is built from
  the real keybindings and so cannot drift from reality.

## Requirements

| Package | Purpose |
|---|---|
| `mpv` | playback engine (required) |
| `python-textual` | interface (required) |
| `python-mutagen` | tags and cover art (required) |
| `yt-dlp` | YouTube search and downloads |
| `python-dbus` | desktop media widget integration (optional) |
| `cava` | visualizer |
| `python-textual-image` | sixel cover art |

Lyrics come from [LRCLIB](https://lrclib.net) — open, no API key, and cached so
the same song is never requested twice.

A sixel-capable terminal (foot, kitty, WezTerm) is needed for cover art. Without
one the side panel still works, just without pictures.

## Install

```bash
git clone https://github.com/<user>/musicbox.git
cd musicbox
install -Dm755 bin/musicbox ~/.local/bin/musicbox
install -Dm755 bin/music    ~/.local/bin/music
```

Make sure `~/.local/bin` is on your `PATH`.

## Use

```bash
musicbox
```

The buttons in the bottom bar are playback controls. Actions that work on a
single song — play, queue, album, download, delete — live in the side panel and
change with the open tab. Press `,` for settings and `?` for every shortcut.

### `music` — the CLI companion

`bin/music` is a separate shell script for quick use without opening the full
interface. musicbox calls it to download, so the yt-dlp logic lives in one place.

```bash
music -s "song title"      search, pick with fzf, play
music -d "song title"      download to ~/Music
music -r "song title"      radio, following recommendations
music -p                   tmux panel: menu + visualizer
```

## Tests

```bash
python3 test_musicbox.py
```

Uses Textual's own `run_test()`, so no real terminal is needed. It checks 125
things: every keybinding has a handler and raises nothing, tab switching, the
queue, albums, the contextual action panel, cover extraction, the commands radio
sends, MPRIS registration, the download progress cell, lyrics parsing, and
recovery after mpv is killed mid-song.

The suite deliberately stays off the network so it is fast and does not depend on
YouTube. The networked paths — search, streaming, radio, and real mp3 and opus
downloads with codec, cover art, and metadata verified — are tested separately
and were run in full before release.

## Design notes

Decisions that are invisible from the outside, written down because each one
took a while to find:

- **mpv runs in idle mode** and is driven over JSON IPC rather than exec'd per
  song. The process stays alive between songs, so its state can be watched and
  controlled at any time.
- **Only one instance may run.** Every instance uses the same mpv socket; a
  second one overwrites the first's socket and leaves it without control, on top
  of fighting over audio and registering MPRIS twice.
- **Cover art in Ogg/Opus files** is stored as a base64 FLAC Picture block inside
  the `metadata_block_picture` Vorbis comment — not `APIC` (ID3), `covr` (MP4),
  or `.pictures` (FLAC). All four paths are handled.
- **`SixelImage` is forced** instead of `AutoImage`; auto-detection can fall back
  to a Unicode block renderer whose output is coarse.
- **`background: transparent` everywhere**, with the `ansi-dark` theme. Textual's
  default themes paint a solid background, which destroys terminal transparency.
- **`yt-dlp --print` does not interpret `\t`** — the column separator has to be a
  real tab character.
- **Radio has to ask for `yes-playlist`.** mpv passes `--no-playlist` to yt-dlp by
  default, so a Mix URL (`&list=RD…`) loads only its first song — radio that
  stops after one track, the exact opposite of the point. Measured on one Mix:
  **1 song without the option, 509 with it.** It is sent per-file through
  `loadfile` rather than to the whole mpv process, so ordinary URLs that happen
  to carry `list=` keep their behaviour.
- **MPRIS is registered by musicbox itself; the mpv-mpris plugin is not used.**
  Version 1.2 (released 2023) on mpv 0.41 occasionally kills mpv during a track
  change: the `cplugin/mpris2` thread builds a `PropertiesChanged` signal from
  metadata strings mpv is in the middle of replacing, GLib finds invalid UTF-8 in
  `append_value_to_blob`, and calls `abort()`. The process becomes a zombie and
  the music stops mid-album while the interface still shows the last title — it
  looks like a frozen app when what died is underneath it. Measured here: **3 of
  30 track changes failed with the plugin, 0 of 30 without.** Since the desktop
  icon was still wanted, musicbox registers on D-Bus itself through
  `python-dbus`, on its own thread with a GLib main loop. Text is sanitised first
  (`dbus_safe`) so the same mistake does not simply change hands. Without
  `python-dbus` musicbox still runs — just without the icon.
- **Declining to pass `--script=` is not enough.** The mpv-mpris package installs
  a symlink at `/etc/mpv/scripts/mpris.so`, and mpv loads that directory for
  every invocation. `--load-scripts=no` is what actually disables it. Before this
  was found, the "disabled" plugin was still being loaded and still taking mpv
  down.
- **Square brackets are not used for the progress bar.** DataTable renders its
  contents as Rich markup, and `[####----]` is swallowed whole as a tag — the bar
  vanished from the screen even though the data was there. The bar uses `━` and
  `─` now.
- **Download progress is read from numbers, not prose.** `music` calls yt-dlp
  with `--progress-template` when its output is not a terminal, so musicbox gets
  raw bytes and seconds and computes percent, speed, and ETA itself. Guessing
  from human-readable text is fragile: the format shifts and it sometimes prints
  "Unknown" in the middle of a perfectly healthy download.
- **Titles are NFKD-normalised before looking up lyrics.** YouTube channels love
  decorative non-ASCII letters — "𝑮𝒐𝒍𝒅𝒆𝒏 𝑩𝒓𝒐𝒘𝒏" reads like an ordinary word to the
  eye but matches nothing in a search.
- **`like_count` is not part of search.** It demands a full extraction per video,
  around five seconds a title — two minutes just to fill one screen of results.
  `view_count` comes free with `--flat-playlist`, so views go in the table and
  likes are fetched afterwards only for the row actually highlighted.
- **Songs you already have are marked `⭳`, and a second download is held once.**
  Matched first by the URL in the download log — the most reliable signal — then
  by NFKD-normalised title against the filenames in `~/Music`, since yt-dlp uses
  the title as the filename. Press `d` again if you really do want another copy.
- **One overlay, not four surfaces.** Textual's built-in help panel docks to the
  right and competes with the info panel — two columns of text side by side, both
  demanding to be read, on top of a footer and a command palette also asking for
  attention. `?` now leads to the same Settings overlay, straight at the Controls
  category. Only one thing is being read at a time.
- **The command palette is switched off.** It lists Textual's own internal
  commands — Maximize, Screenshot, Theme — which have nothing to do with playing
  music, and it was a fourth surface offering them.
- **Footer labels do not name their own key.** Textual already prints the key
  ahead of the description; a label that names it too renders as `? ? Help`.
- **Settings were grouped from the start.** A single long list only grows with
  every new option, and the rarely-used ones end up in the way of the frequent
  ones.
- **The test suite rejects conflicting keybindings.** `plus` was once bound
  twice — volume and density — and the later one died silently with no message at
  all. The suite now refuses that state, and checks that every bound action
  actually has a handler.
- **`MUSICBOX_AO` forces the audio output.** Tests use `null`. Without it the
  suite fights the musicbox you are actually listening to for the audio device,
  mpv fails to open a stream (`Device or resource busy`), the song never plays,
  and the results mislead — a failure that looks exactly like an application bug
  and is not.
- **mpv is watched and restarted.** Because a death like the one above can come
  from anywhere — a third-party plugin, the OOM killer, a decoder giving up — the
  process is checked every second. If it died, it comes back with the same
  playlist, song, second, and loop setting.
- **Every IPC connection carries a generation number.** After mpv is restarted the
  old reader task has to actually stop. Otherwise two tasks call `readline()` on
  the same `StreamReader`, asyncio refuses, and property updates stop flowing —
  the same freeze, with the cause merely moved inside the application.
- **mpv IPC can ask, not only tell.** Replies arrive mixed into the event stream,
  so each request is matched by `request_id`; without that, what gets read may be
  some other event that happened to arrive first. The Radio panel reads mpv's
  playlist through this path.
- **Recommendations do not pretend to be an algorithm.** They come from the
  YouTube Mixes of the songs you liked, minus what you already have, sorted by
  view count. That is YouTube's "people who liked this also listened to that" —
  useful, and honest about where it comes from.
- **Panel hints are lambdas, not strings.** As plain strings they are evaluated
  when the module loads and freeze in whichever language was active at startup,
  so switching language would not change them.

## Licence

MIT
