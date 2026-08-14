import asyncio, os, signal, sys, tempfile, traceback
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

# Audio diarahkan ke null: suite ini memutar lagu sungguhan, dan berebut
# perangkat dengan musicbox yang sedang dipakai mendengarkan musik membuat mpv
# gagal membuka stream — lagunya tidak jadi diputar dan hasil ujinya menyesatkan.
os.environ.setdefault("MUSICBOX_AO", "null")

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
        # Plugin mpv-mpris sengaja tidak dipakai: versinya di sistem ini
        # membunuh mpv di sebagian perpindahan lagu. Menahan diri dari
        # `--script=` saja tidak cukup, karena paketnya memasang symlink di
        # /etc/mpv/scripts/ yang dimuat mpv tanpa diminta.
        args = Path(f"/proc/{app.player.proc.pid}/cmdline").read_bytes().decode(
            errors="replace").split("\0")
        check("plugin mpv-mpris benar-benar tidak dimuat",
              "--load-scripts=no" in args and not app.player.mpris)
        # Ikon di widget media desktop tetap ada, tapi didaftarkan musicbox
        # sendiri lewat D-Bus, bukan menumpang proses yang bisa ikut mati.
        check("musicbox mendaftar sendiri sebagai pemutar MPRIS",
              app.mpris is not None and app.mpris.aktif,
              "aktif" if (app.mpris and app.mpris.aktif) else
              "tidak aktif (python-dbus tidak ada?)")
        check("teks tak sah tidak diteruskan ke D-Bus",
              mod.dbus_safe("a\udcffb") == "a?b", repr(mod.dbus_safe("a\udcffb")))

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

        # Progres unduhan: barnya harus selamat melewati markup Rich. Kurung
        # siku pernah dipakai sebagai bingkai, dan Rich menelannya sebagai tag
        # sehingga barnya hilang dari layar padahal datanya ada.
        from rich.markup import render as _render
        entri = {"status": "berjalan"}
        mod.parse_progress("MBPROG|9961472|19965952|NA|454824.0|22", entri)
        sel = _render(mod.progress_cell(entri)).plain
        check("bar progres tidak ditelan markup", "━" in sel and "─" in sel, sel[:30])
        check("progres memuat persen, ukuran, kecepatan, sisa",
              all(x in sel for x in ("49.9%", "MiB", "/s", "sisa")), sel[-26:])
        check("progres selesai tidak menyisakan bar",
              mod.progress_cell({"status": "selesai"}) == "selesai")

        # Lirik: LRC diurutkan menurut waktu, judul dibersihkan dari embel-embel.
        baris = mod.parse_lrc("[00:20.84]satu\n[01:05.00]tiga\n[00:45.10]dua")
        check("LRC terurut menurut waktu",
              [b[1] for b in baris] == ["satu", "dua", "tiga"])
        _, judul = mod.bersihkan_judul("Golden Brown - The Stranglers | 1 Hour Loop")
        check("judul dibersihkan dari embel-embel",
              "Hour" not in judul and "Loop" not in judul, repr(judul))
        check("lirik yang belum pernah dicari kembali None",
              mod.lyrics_cached("lagu yang pasti tidak ada xyzzy", "", 0) is None)
        # Kanal YouTube gemar memakai huruf hias di luar ASCII. Tanpa
        # normalisasi, judul seperti ini tidak cocok dengan apa pun.
        _, hias = mod.bersihkan_judul(
            "\U0001d47e\U0001d490\U0001d48d\U0001d489\U0001d486\U0001d489 "
            "\U0001d475\U0001d493\U0001d490\U0001d498\U0001d489 - "
            "\U0001d47b\U0001d489\U0001d486")
        check("huruf hias dinormalkan jadi huruf biasa", hias == "The",
              repr(hias))

        # Penanda ▶ dan ♪ berbagi kolom judul; keduanya harus bertahan bersama.
        lagu = dict(app.library.tracks[0])
        app._lyr_mark[lagu["path"]] = True
        label = app._label_library(lagu, lagu["path"])
        check("penanda berbunyi dan lirik hidup berdampingan",
              "▶" in label and "♪" in label and lagu["title"][:12] in label,
              label[:30])

        # Panel kanan tidak boleh kosong melompong saat tidak ada yang disorot.
        app.query_one("#tabs").active = "tab-yt"
        await pilot.pause(0.3)
        app.update_info("results", -1)
        await pilot.pause(0.2)
        petunjuk = str(app.query_one("#info-text", Static).content)
        check("panel kosong memberi petunjuk", "Search YouTube" in petunjuk,
              petunjuk[:26].replace("\n", " "))
        # Petunjuk panel ikut berganti bahasa, bukan tertinggal satu bahasa.
        mod.simpan_bahasa("id")
        check("petunjuk panel ikut diterjemahkan",
              "Cari di YouTube" in app.PETUNJUK["results"](),
              app.PETUNJUK["results"]()[:26].replace("\n", " "))
        mod.simpan_bahasa("en")

        # Lagu yang berkasnya sudah ada tidak boleh terunduh dua kali.
        lagu0 = app.library.tracks[0]
        sama = {"id": "a" * 11, "title": Path(lagu0["path"]).stem}
        beda = {"id": "b" * 11, "title": "lagu yang pasti belum ada xyzzy"}
        check("lagu yang sudah ada terdeteksi",
              app.sudah_diunduh(sama) is not None)
        check("lagu baru tidak salah terdeteksi",
              app.sudah_diunduh(beda) is None)

        # Footer adalah pintu masuk, bukan katalog perintah. Semua aksi
        # pemutaran sudah punya tombol berkotak tepat di atasnya.
        tampil = [b for b in app.BINDINGS if getattr(b, "show", False)]
        check("footer ringkas", len(tampil) <= 4, f"{len(tampil)} entri")
        label = " ".join(b.description for b in tampil)
        check("footer memuat Settings", "Settings" in label, label[:40])
        # "?" sengaja TIDAK diikat. textual-image menanyai terminal dan sisa
        # balasannya (ESC [ ? 62 ; 4 c) sampai ke Textual sebagai tombol — "?"
        # yang terikat aksi akan menjalankannya sendiri saat aplikasi dibuka.
        check("tombol ? tidak diikat",
              not any(b.key == "question_mark" for b in app.BINDINGS))
        # Footer sudah mencetak tombolnya; label yang ikut menyebut tombol
        # membuatnya tercetak dua kali ("? ? Help").
        check("label footer tidak mengulang tombolnya",
              not any(b.description.strip().startswith(("?", ",", "^"))
                      for b in tampil), label[:40])

        # Tombol yang terikat dua kali membuat yang belakangan mati diam-diam —
        # persis yang pernah terjadi pada plus/minus (volume vs kerapatan).
        kunci = [b.key for b in app.BINDINGS]
        ganda = {k for k in kunci if kunci.count(k) > 1}
        check("tidak ada keybind bentrok", not ganda, str(ganda) or "bersih")
        hilang = [b.action for b in app.BINDINGS
                  if not hasattr(app, f"action_{b.action}")]
        check("semua aksi terikat punya handler", not hilang, str(hilang) or "lengkap")

        # Tidak boleh ada teks Indonesia bocor saat antarmuka berbahasa Inggris.
        mod.simpan_bahasa("en")
        bocor = [b.description for b in app.BINDINGS if b.description and
                 any(w in b.description for w in
                     ("Pindai", "Batal", "Kembali", "Antrean", "Naik", "Turun",
                      "Hapus", "Putar", "Unduh", "Muat", "Urutkan", "Buang"))]
        check("tidak ada teks Indonesia bocor di mode Inggris",
              not bocor, str(bocor[:3]) or "bersih")

        # Layar Settings: tiap kategori punya isi, dan opsinya benar-benar
        # mengubah keadaan aplikasi (bukan sekadar menampilkan nilai).
        app.action_settings()
        await pilot.pause(0.8)
        layar = app.screen
        check("layar Settings terbuka", isinstance(layar, mod.SettingsScreen),
              type(layar).__name__)
        if isinstance(layar, mod.SettingsScreen):
            for kat in layar.KATEGORI:
                await layar._terapkan(f"nav:{kat}")
                await pilot.pause(0.2)
                check(f"kategori {kat} terisi", len(layar.query(".opsi")) >= 1)
            await layar._terapkan("nav:Appearance")
            await pilot.pause(0.2)
            sebelum = app.cava_on
            await layar._terapkan("cava")
            await pilot.pause(0.3)
            check("opsi Settings mengubah keadaan sungguhan",
                  app.cava_on != sebelum, f"{sebelum} -> {app.cava_on}")
            # Dikembalikan: tata letak panel bergantung pada cava, dan
            # pemeriksaan kerapatan di bawah membaca tinggi sampul.
            await layar._terapkan("cava")
            await pilot.pause(0.3)
            layar.action_close()
            await pilot.pause(0.4)
            check("bisa keluar dari Settings",
                  not isinstance(app.screen, mod.SettingsScreen))

        # Label panel info ikut bahasa, bukan tertinggal dalam satu bahasa.
        mod.simpan_bahasa("id")
        check("label panel info ikut diterjemahkan",
              mod._("artist") == "artis" and mod._("duration") == "durasi",
              f"{mod._('artist')} / {mod._('duration')}")
        mod.simpan_bahasa("en")
        check("label panel info kembali Inggris", mod._("artist") == "artist")

        # Notifikasi ikut bahasa juga — itu teks yang paling sering muncul
        # sekilas, dan paling mudah tertinggal saat menambah fitur.
        contoh = ["queue is empty", "download finished", "library rescanned",
                  "sorted by views", "nothing playing yet", "shuffled",
                  "radio started", "deleted"]
        mod.simpan_bahasa("id")
        belum = [k for k in contoh if mod._(k) == k]
        check("notifikasi punya terjemahan", not belum, str(belum) or "lengkap")
        mod.simpan_bahasa("en")

        # "?" bermuara ke overlay yang sama, langsung di kategori Kontrol —
        # bukan panel tempel terpisah yang berebut ruang dengan panel info.
        app.action_help()
        await pilot.pause(0.6)
        bantuan = app.screen
        check("? membuka overlay yang sama",
              isinstance(bantuan, mod.SettingsScreen)
              and bantuan.kategori == "Controls",
              f"{type(bantuan).__name__}/{getattr(bantuan, 'kategori', '-')}")
        if isinstance(bantuan, mod.SettingsScreen):
            n = len(bantuan.query(".opsi"))
            check("daftar pintasan terisi dari BINDINGS", n >= 20, f"{n} pintasan")
            bantuan.action_close()
            await pilot.pause(0.4)

        # Bahasa: Inggris bawaan, terjemahan bekerja, teks asing tetap terbaca.
        mod.simpan_bahasa("en")
        check("bahasa bawaan Inggris", mod._("Search") == "Search")
        mod.simpan_bahasa("id")
        check("terjemahan Indonesia bekerja", mod._("Queue") == "Antrean",
              mod._("Queue"))
        check("teks tanpa terjemahan tidak hilang",
              mod._("Totally Untranslated") == "Totally Untranslated")
        mod.simpan_bahasa("en")

        # Lagu disukai: simpan, tolak duplikat, buang, pulih dari berkas.
        app.liked = []
        app.query_one("#tabs").active = "tab-lib"
        await pilot.pause(0.3)
        app.query_one("#library", DataTable).move_cursor(row=0)
        await pilot.pause(0.2)
        app.action_like()
        await pilot.pause(0.3)
        check("lagu bisa disukai", len(app.liked) == 1)
        app.action_like()
        await pilot.pause(0.2)
        check("duplikat suka ditolak", len(app.liked) == 1)
        app.save_liked()
        app.liked = []
        app.load_liked()
        check("daftar suka pulih dari berkas", len(app.liked) == 1)

        # Penanda radio: mati saat memutar biasa, menyala saat radio.
        app.player.radio = False
        app._sync_radio_button()
        check("penanda radio mati saat bukan radio",
              app.query_one("#btn-radio").has_class("off"))
        app.player.radio = True
        app._sync_radio_button()
        check("penanda radio menyala saat radio",
              app.query_one("#btn-radio").has_class("on"))
        app.player.radio = False

        # Kerapatan tampilan naik bertingkat dan berhenti di batas.
        tinggi = []
        for target in (0, 1, 2):
            while app.zoom != target:
                (app.action_zoom_in if app.zoom < target else app.action_zoom_out)()
            await pilot.pause(0.2)
            tinggi.append(app._tinggi_sampul())
        check("kerapatan menaikkan tinggi sampul",
              tinggi == sorted(tinggi) and tinggi[0] < tinggi[2], str(tinggi))
        app.action_zoom_in()
        check("kerapatan berhenti di batas atas", app.zoom == 2)

        # Radio harus meminta yt-dlp membuka daftar Mix. Tanpa yes-playlist mpv
        # cuma memuat lagu pertamanya dan radionya berhenti di situ. Diperiksa
        # dari perintah yang dikirim, bukan lewat jaringan, supaya tetap cepat
        # dan tidak bergantung pada YouTube.
        sent = []
        _asli = app.player._send
        async def _rekam(payload):
            sent.append(payload)
            return await _asli(payload)
        app.player._send = _rekam
        try:
            await app.player.play_radio("https://www.youtube.com/watch?v=X&list=RDX")
        finally:
            app.player._send = _asli
        muat = [p for p in sent if p.get("command", [None])[0] == "loadfile"]
        check("radio mengirim loadfile", len(muat) == 1, f"{len(muat)} perintah")
        opsi = muat[0]["command"][4] if muat and len(muat[0]["command"]) > 4 else {}
        check("radio memakai yes-playlist",
              opsi.get("ytdl-raw-options") == "yes-playlist=", str(opsi))

        # mpv yang mati mendadak tidak boleh berubah jadi aplikasi yang membeku.
        # Ini ditaruh paling akhir karena sengaja membunuh mesin pemutarnya.
        tracks = app.library.tracks[:3]
        if tracks:
            app.queue = [{"title": t["title"], "target": t["path"],
                          "source": "lokal"} for t in tracks]
            await app.action_play_queue(loop=True)
            await pilot.pause(3.0)
            old_pid = app.player.proc.pid
            old_path = app.player.state.get("path")
            os.kill(old_pid, signal.SIGABRT)
            await pilot.pause(4.5)
            check("mpv dibangkitkan setelah mati",
                  app.player.proc.pid != old_pid and app.player.proc.poll() is None)
            check("lagu yang sama disambung",
                  app.player.state.get("path") == old_path)
            check("playlist & loop dipulihkan",
                  len(app.player.playlist) == len(tracks) and app.player.loop)
            t1 = app.player.state.get("time-pos") or 0
            await pilot.pause(2.0)
            check("pemutaran jalan lagi setelah pulih",
                  (app.player.state.get("time-pos") or 0) > t1)
        app.player.shutdown()

asyncio.run(main())

print()
for name, ok, detail in checks:
    print(f"  {'✓' if ok else '✗'} {name}" + (f"  — {detail}" if detail else ""))
print(f"\n  {len(checks)-len(fails)}/{len(checks)} lolos")
if fails:
    print("  GAGAL:", ", ".join(fails))
    sys.exit(1)
