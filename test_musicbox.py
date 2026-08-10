import asyncio, os, sys, tempfile, traceback
from pathlib import Path

# Socket & state terpisah supaya tidak bentrok dengan instans yang sedang jalan.
tmp = tempfile.mkdtemp(prefix="mbtest-")
os.environ["XDG_RUNTIME_DIR"] = tmp

# Uji salinan di repo ini, bukan yang terpasang di ~/.local/bin, supaya hasilnya
# mencerminkan kode yang benar-benar ada di sini.
SRC = Path(__file__).parent / "bin" / "musicbox"
src = SRC.read_text().replace("raise SystemExit(main())", "pass")
mod = type(sys)("mb")
exec(compile(src, str(SRC), "exec"), mod.__dict__)
mod.STATE_DIR = Path(tmp) / "state"
mod.QUEUE_FILE = mod.STATE_DIR / "queue.json"
mod.PLAYLIST_DIR = mod.STATE_DIR / "playlists"
mod.RESUME_FILE = mod.STATE_DIR / "resume.json"
mod.DOWNLOADS_LOG = mod.STATE_DIR / "downloads.json"
mod.LIBRARY_CACHE = mod.STATE_DIR / "library.json"
mod.MPV_SOCKET = Path(tmp) / "mpv.sock"

fails, checks = [], []
def check(name, cond, detail=""):
    checks.append((name, bool(cond), detail))
    if not cond:
        fails.append(name)

async def main():
    app = mod.MusicBox()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(2.0)
        from textual.widgets import DataTable, Tree, Static

        check("aplikasi hidup", app.is_running)
        check("mpv tersambung", app.player.writer is not None)
        check("mpris dimuat", app.player.mpris)

        lib = app.query_one("#library", DataTable)
        check("library terisi", lib.row_count > 0, f"{lib.row_count} baris")
        for tid in ("results", "queue", "downloads"):
            t = app.query_one(f"#{tid}", DataTable)
            check(f"tabel {tid} punya kolom", len(t.columns) > 0)
        check("tree playlist ada", app.query_one("#pltree", Tree) is not None)

        # Semua aksi keybind harus punya handler dan tidak melempar exception.
        for b in app.BINDINGS:
            name = f"action_{b.action}"
            check(f"handler {b.action}", hasattr(app, name))

        # Jalankan aksi yang aman (tidak menghapus / tidak butuh jaringan).
        for act in ("toggle_autoplay", "toggle_cava", "toggle_format",
                    "enqueue", "queue_up", "queue_down", "dequeue", "rescan",
                    "delete_playlist", "remove_from_album"):
            try:
                r = getattr(app, f"action_{act}")()
                if asyncio.iscoroutine(r):
                    await r
                await pilot.pause(0.1)
                check(f"aksi {act}", True)
            except Exception as exc:
                check(f"aksi {act}", False, f"{type(exc).__name__}: {exc}")

        # Pindah tab dan pastikan panel info ikut.
        for tab in ("tab-yt", "tab-queue", "tab-pl", "tab-dl", "tab-lib"):
            try:
                app.query_one("#tabs").active = tab
                await pilot.pause(0.2)
                check(f"tab {tab}", True)
            except Exception as exc:
                check(f"tab {tab}", False, f"{type(exc).__name__}: {exc}")

        # Antrean: tambah dari library lalu simpan playlist.
        app.query_one("#tabs").active = "tab-lib"
        await pilot.pause(0.2)
        app.action_enqueue()
        await pilot.pause(0.2)
        check("antrean bertambah", len(app.queue) > 0, f"{len(app.queue)} item")
        app._do_new_playlist("uji")
        await pilot.pause(0.3)
        check("album dibuat", "uji" in app.playlists)

        # Rantai: buat album lalu langsung isi lagu yang disorot.
        app.query_one("#tabs").active = "tab-lib"
        await pilot.pause(0.2)
        app._pending_add = app._selected_song()
        check("lagu terpilih terbaca", app._pending_add is not None)
        app._append_to_album("uji", app._pending_add)
        await pilot.pause(0.3)
        check("lagu masuk album", len(app.playlists.get("uji", [])) > 0,
              f"{len(app.playlists.get('uji', []))} lagu")

        # Duplikat harus ditolak.
        before_dup = len(app.playlists.get("uji", []))
        app._append_to_album("uji", app._pending_add)
        await pilot.pause(0.3)
        check("duplikat ditolak", len(app.playlists.get("uji", [])) == before_dup,
              f"{before_dup} tetap {len(app.playlists.get('uji', []))}")

        # Enter pada album tidak boleh ikut melipatnya.
        from textual.widgets import Tree as T0
        check("auto_expand mati", app.query_one("#pltree", T0).auto_expand is False)

        # Memutar daun album harus memuat SELURUH album ke antrean, bukan
        # satu lagu saja — kalau tidak, tombol "berikut" tidak punya tujuan.
        import json as _json
        two = [{"title": t["title"], "target": t["path"], "source": "lokal"}
               for t in app.library.tracks[:2]]
        (mod.PLAYLIST_DIR / "multi.json").write_text(_json.dumps(two))
        app.load_playlists(); await pilot.pause(0.4)
        from textual.widgets import Tree as T1
        tr = app.query_one("#pltree", T1)
        node = next(n for n in tr.root.children if "multi" in str(n.label))
        leaf2 = node.children[1]
        tr.focus(); tr.move_cursor(leaf2); await pilot.pause(0.2)
        tr.action_select_cursor(); await pilot.pause(1.0)
        check("putar daun memuat album", len(app.queue) == 2, f"{len(app.queue)} lagu")
        check("mulai dari lagu yang dipilih",
              app.queue and app.queue[0]["target"] == two[1]["target"])

        # Indikator lagu yang sedang diputar.
        app._mark_now_playing(two[1]["target"])
        await pilot.pause(0.3)
        marked = [str(l.label) for n in tr.root.children for l in n.children
                  if str(l.label).startswith("▶")]
        check("indikator lagu aktif", len(marked) == 1, f"{len(marked)} baris ditandai")

        # Keluarkan lagu dari album lewat node daun di tree.
        app.query_one("#tabs").active = "tab-pl"
        await pilot.pause(0.4)
        from textual.widgets import Tree as T
        tree = app.query_one("#pltree", T)
        leaf = None
        for node in tree.root.children:
            for child in node.children:
                leaf = child; break
        if leaf is not None:
            # move_cursor() yang memindahkan cursor_node; select_node() dan
            # menyetel cursor_line tidak melakukannya.
            tree.move_cursor(leaf)
            await pilot.pause(0.2)
            check("kursor tree pindah ke daun",
                  (tree.cursor_node.data or {}).get("item") is not None)
            before = len(app.playlists.get("uji", []))
            app.action_remove_from_album()
            await pilot.pause(0.4)
            after = len(app.playlists.get("uji", []))
            check("keluarkan dari album", after < before, f"{before} -> {after}")
        else:
            check("keluarkan dari album", False, "daun tidak ketemu")

        # check_action harus menyembunyikan aksi yang tidak relevan per tab.
        app.query_one("#tabs").active = "tab-dl"
        await pilot.pause(0.2)
        check("footer kontekstual", app.check_action("download", None) is False)

        # Panel aksi lagu harus ikut berganti per tab.
        from textual.containers import Vertical as V
        for tab, expect in (("tab-lib", 4), ("tab-yt", 5), ("tab-queue", 3),
                            ("tab-pl", 3), ("tab-dl", 0)):
            app.query_one("#tabs").active = tab
            await pilot.pause(0.3)
            n = len(app.query_one("#song-actions", V).children)
            check(f"aksi lagu {tab}", n == expect, f"{n} tombol")
        app.query_one("#tabs").active = "tab-yt"
        await pilot.pause(0.2)
        check("aksi unduh muncul di tab Cari", app.check_action("download", None) is True)

        # Sampul: ekstraksi dari file lokal tidak boleh melempar exception.
        try:
            c = mod.extract_cover(Path(app.library.tracks[0]["path"]))
            check("ekstraksi sampul", True, str(c and c.name))
        except Exception as exc:
            check("ekstraksi sampul", False, f"{type(exc).__name__}: {exc}")

asyncio.run(main())

print()
for name, ok, detail in checks:
    print(f"  {'✓' if ok else '✗'} {name}" + (f"  — {detail}" if detail else ""))
print(f"\n  {len(checks)-len(fails)}/{len(checks)} lolos")
if fails:
    print("  GAGAL:", ", ".join(fails))
    sys.exit(1)
