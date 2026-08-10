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
- **MPRIS**, sehingga tampil di widget media desktop dan bisa dikendalikan dari
  sana.
- **Lanjut dari terakhir** — lagu dan posisi dipulihkan saat dibuka lagi.

## Kebutuhan

| Paket | Kegunaan |
|---|---|
| `mpv` | mesin pemutar (wajib) |
| `python-textual` | antarmuka (wajib) |
| `python-mutagen` | baca tag & sampul (wajib) |
| `yt-dlp` | cari dan unduh dari YouTube |
| `mpv-mpris` | tampil di widget media desktop |
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
Memeriksa 60 hal: semua handler keybind ada dan tidak melempar exception,
perpindahan tab, antrean, album, panel aksi kontekstual, dan ekstraksi sampul.

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

## Lisensi

MIT
