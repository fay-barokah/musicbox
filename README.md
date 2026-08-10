# musicbox

Pemutar musik TUI untuk Linux. Library lokal, pencarian dan unduhan YouTube,
antrean, album, visualizer, dan sampul sungguhan di terminal.

Warnanya mengikuti skema [Caelestia Shell](https://github.com/caelestia-dots/shell)
kalau tersedia, dan jatuh ke palet cadangan kalau tidak.

```
┌ Library │ Cari │ Antrean │ Album │ Unduhan ─────────┬──────────────┐
│                                                      │  [sampul]    │
│  Judul                        Artis      Durasi      │              │
│  ...                                                 │  ▶  putar    │
│                                                      │  ＋ antrean  │
│                                                      │  ♪  album    │
├──────────────────────────────────────────────────────┴──────────────┤
│  ▁▂▄▆█▆▄▂▁  ▂▄▆█▇▅▃▁  (cava)                                        │
├─────────────────────────────────────────────────────────────────────┤
│  ▶ Judul lagu      ⏮ ⏸ ⏭ ⏹ ⇄ ↻auto ◫cava  🕪 ▬▬▬▬            3:35 │
└─────────────────────────────────────────────────────────────────────┘
```

## Fitur

- **Library** dari `~/Music` dengan tag dibaca lewat mutagen, di-cache supaya
  start berikutnya instan.
- **Cari & putar dari YouTube**, dengan radio yang menyambung ke rekomendasi.
- **Unduh** ke `~/Music` sebagai mp3 atau opus, lengkap dengan sampul dan
  metadata tertanam.
- **Antrean** yang bisa diurutkan, dan **album** tersimpan berbentuk pohon.
- **Visualizer** membaca keluaran mentah cava.
- **Sampul sungguhan** lewat sixel, bukan blok ASCII.
- **Penanda lagu aktif** di daftar library, antrean, dan album.
- **Lanjut dari terakhir** — lagu dan posisi dipulihkan saat dibuka lagi.
- **Unduhan bergaya pacman** — bar progres, ukuran, kecepatan, dan sisa waktu,
  bergerak langsung di tab Unduhan.
- **Tahan banting**: kalau mpv mati mendadak, musicbox menghidupkannya lagi di
  lagu dan detik yang sama, bukan membeku diam-diam.
- **MPRIS bawaan** — musicbox mendaftar sendiri ke D-Bus, jadi tampil di widget
  media desktop lengkap dengan judul, sampul, dan tombol, tanpa menumpang
  plugin mpv yang bisa menjatuhkan pemutarnya.

## Kebutuhan

| Paket | Kegunaan |
|---|---|
| `mpv` | mesin pemutar (wajib) |
| `python-textual` | antarmuka (wajib) |
| `python-mutagen` | baca tag & sampul (wajib) |
| `yt-dlp` | cari dan unduh dari YouTube |
| `python-dbus` | tampil di widget media desktop (opsional) |
| `cava` | visualizer |
| `python-textual-image` | sampul sixel |

Terminal yang mendukung sixel (mis. foot, kitty, WezTerm) dibutuhkan untuk
menampilkan sampul. Tanpa itu panel kanan tetap jalan, hanya tanpa gambar.

## Pasang

```bash
git clone https://github.com/<user>/musicbox.git
cd musicbox
install -Dm755 bin/musicbox ~/.local/bin/musicbox
install -Dm755 bin/music    ~/.local/bin/music
```

Pastikan `~/.local/bin` ada di `PATH`.

## Pakai

```bash
musicbox
```

Tombol yang tampil di bar bawah adalah kendali pemutaran. Aksi yang bekerja
pada satu lagu — putar, antrean, album, unduh, hapus — ada di panel kanan dan
berganti mengikuti tab yang dibuka.

### `music` — pendamping berbasis CLI

`bin/music` adalah skrip shell terpisah untuk pemakaian cepat tanpa membuka
antarmuka penuh. musicbox memanggilnya untuk mengunduh, sehingga logika yt-dlp
hanya ada di satu tempat.

```bash
music -s "judul lagu"      cari, pilih lewat fzf, putar
music -d "judul lagu"      unduh ke ~/Music
music -r "judul lagu"      radio, mengikuti rekomendasi
music -p                   panel tmux: menu + visualizer
```

## Uji

```bash
python3 test_musicbox.py
```

Memakai `run_test()` bawaan Textual, jadi tidak butuh terminal sungguhan.
Memeriksa 76 hal: semua handler keybind ada dan tidak melempar exception,
perpindahan tab, antrean, album, panel aksi kontekstual, ekstraksi sampul,
perintah yang dikirim radio, pendaftaran MPRIS, dan pemulihan setelah mpv
dibunuh di tengah lagu.

Suite ini sengaja tidak menyentuh jaringan supaya cepat dan tidak bergantung
pada YouTube. Jalur berjaringan — pencarian, streaming, radio, dan unduhan mp3
serta opus lengkap dengan pemeriksaan codec, sampul, dan metadata — diuji
terpisah dan pernah dijalankan penuh sebelum rilis.

## Catatan teknis

Beberapa keputusan yang tidak terlihat dari luar, dicatat karena sempat memakan
waktu untuk ditemukan:

- **mpv dijalankan dalam mode idle** dan dikendalikan lewat JSON IPC, bukan
  di-exec per lagu. Prosesnya tetap hidup di antara lagu sehingga status bisa
  dipantau dan dikendalikan kapan saja.
- **Instans tunggal dikunci.** Semua instans memakai socket mpv yang sama;
  instans kedua akan menimpa socket milik yang pertama dan membuatnya kehilangan
  kendali, selain berebut audio dan mendaftarkan MPRIS ganda.
- **Sampul di file Ogg/Opus** disimpan sebagai blok Picture FLAC ter-base64 di
  dalam Vorbis comment `metadata_block_picture` — bukan `APIC` (ID3), `covr`
  (MP4), atau `.pictures` (FLAC). Keempat jalur ditangani.
- **`SixelImage` dipaksa** alih-alih `AutoImage`; deteksi otomatis bisa jatuh ke
  renderer blok Unicode yang hasilnya kasar.
- **`background: transparent`** di semua widget, dan tema `ansi-dark`. Tema
  bawaan Textual mengecat latar solid sehingga transparansi terminal hilang.
- **`yt-dlp --print` tidak menafsirkan `\t`** — pemisah kolom harus berupa
  karakter tab sungguhan.
- **Radio harus meminta `yes-playlist`.** mpv memberi `--no-playlist` ke yt-dlp
  secara bawaan, jadi URL Mix (`&list=RD…`) hanya memuat lagu pertamanya —
  radio yang berhenti setelah satu lagu, persis kebalikan dari gunanya. Terukur
  pada satu Mix: **1 lagu tanpa opsi ini, 509 dengan.** Opsinya dikirim per-file
  lewat `loadfile`, bukan ke seluruh proses mpv, supaya URL biasa yang kebetulan
  membawa `list=` tidak ikut berubah perilakunya.
- **MPRIS didaftarkan sendiri, plugin mpv-mpris tidak dipakai.** Versi 1.2
  (rilis 2023) di atas mpv 0.41 sesekali membunuh mpv saat lagu berpindah:
  thread `cplugin/mpris2` menyusun sinyal `PropertiesChanged` dari string
  metadata yang sedang diganti mpv, GLib mendapati UTF-8 tak sah di
  `append_value_to_blob`, lalu memanggil `abort()`. Prosesnya jadi zombie dan
  musik berhenti di tengah album, sementara antarmukanya tetap memperlihatkan
  judul terakhir — terlihat seperti aplikasi yang macet padahal yang mati ada di
  bawahnya. Terukur di sini: **3 dari 30 perpindahan lagu gagal dengan plugin,
  0 dari 30 tanpa.** Karena ikon di widget desktop tetap diinginkan, musicbox
  mendaftar sendiri ke D-Bus lewat `python-dbus`, di thread terpisah dengan main
  loop GLib. Teks dibersihkan dulu (`dbus_safe`) supaya kesalahan yang sama
  tidak berpindah tangan. Kalau `python-dbus` tidak ada, musicbox tetap jalan —
  hanya tanpa ikon.
- **Menahan diri dari `--script=` saja tidak cukup.** Paket mpv-mpris memasang
  symlink di `/etc/mpv/scripts/mpris.so`, dan mpv memuat isi direktori itu untuk
  setiap pemakaian tanpa diminta. Yang benar-benar mematikannya adalah
  `--load-scripts=no`. Sebelum ini ketahuan, plugin yang "sudah dimatikan"
  ternyata masih ikut termuat dan masih menjatuhkan mpv.
- **`MUSICBOX_AO` memaksa keluaran audio.** Dipakai pengujian dengan nilai
  `null`. Tanpa itu suite berebut perangkat audio dengan musicbox yang sedang
  benar-benar dipakai mendengarkan musik, mpv gagal membuka stream
  (`Device or resource busy`), lagunya tidak jadi diputar, dan hasil ujinya
  menyesatkan — kegagalan yang tampak seperti bug aplikasi padahal bukan.
- **mpv diawasi dan dihidupkan ulang.** Karena kematian seperti di atas bisa
  datang dari mana saja — plugin pihak ketiga, OOM killer, dekoder yang menyerah
  — proses mpv diperiksa tiap detik. Kalau mati, ia dibangkitkan lagi dengan
  playlist, posisi lagu, detik, dan status loop yang sama.
- **Tiap sambungan IPC punya nomor generasi.** Setelah mpv dihidupkan ulang,
  task pembaca yang lama harus benar-benar berhenti. Kalau tidak, dua task
  memanggil `readline()` pada `StreamReader` yang sama, asyncio menolaknya, dan
  pembaruan properti berhenti mengalir — macet yang sama persis, hanya
  penyebabnya berpindah ke dalam aplikasi sendiri.

## Lisensi

MIT
