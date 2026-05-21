# Panduan Menjalankan Website UkurKu di Raspberry Pi

Panduan ini untuk menjalankan website UkurKu di Raspberry Pi yang sama dengan alat ukur.

Tujuannya sederhana:

```text
alat ukur menghasilkan data → website menampilkan data itu
```

## Langkah 0: Mendapatkan Folder Website

Pastikan Raspberry Pi memiliki dua folder berikut di folder home:

```text
folder home/
├── program-python
└── sorting-system-ukurku
```

Folder `program-python` adalah program alat ukur. Folder `sorting-system-ukurku` adalah website UkurKu.

Jika folder `sorting-system-ukurku` belum ada, minta developer mengirim atau menyalinnya ke Raspberry Pi.

## Persiapan Sekali Saja

Buka Terminal, lalu jalankan:

```bash
cd ~/sorting-system-ukurku
chmod +x setup_raspberry_pi.sh
./setup_raspberry_pi.sh
```

Setup akan mengecek Python, menginstall kebutuhan website, membuat file pengaturan `.env`, mencari folder `program-python`, dan menyiapkan script untuk menjalankan website.

## Cara Pemakaian Sehari-hari

### 1. Jalankan alat ukur

Jalankan program alat ukur seperti biasa dari folder `program-python`.

Setelah alat selesai mengukur, alat akan membuat file hasil terakhir:

```text
program-python/hasil_tahap14/latest_integrated_chargeable.json
```

### 2. Jalankan website

Buka Terminal baru, lalu jalankan:

```bash
cd ~/sorting-system-ukurku
./run_real_mode.sh
```

Terminal akan menampilkan alamat website, misalnya:

```text
http://localhost:5000
http://192.168.1.25:5000
```

### 3. Buka website

Dari Raspberry Pi langsung:

```text
http://localhost:5000
```

Dari HP/laptop satu Wi-Fi:

```text
http://IP-RASPBERRY-PI:5000
```

### 4. Ambil hasil pengukuran

Di website, klik:

```text
Ambil Hasil Pengukuran
```

Jika berhasil, website akan menampilkan hasil dari alat dan menyimpannya ke halaman Riwayat.

## Urutan Singkat

```text
Jalankan alat ukur → jalankan website → buka browser → klik Ambil Hasil Pengukuran
```

## Jika Ada Masalah

| Pesan/Kondisi | Artinya | Yang Dilakukan |
|---|---|---|
| File `.env` tidak ditemukan | Setup belum dijalankan | Jalankan `./setup_raspberry_pi.sh` |
| Flask belum terinstall | Kebutuhan website belum terpasang | Jalankan `./setup_raspberry_pi.sh` |
| File pengukuran tidak ditemukan | Alat belum menghasilkan data | Jalankan alat ukur dulu |
| Data pengukuran terlalu lama | Hasil alat sudah lama | Jalankan pengukuran baru |
| Folder `program-python` tidak ditemukan | Letak folder backend berbeda | Edit `.env`, isi lokasi folder `program-python` |
| Website tidak bisa dibuka dari HP/laptop | Perangkat tidak satu Wi-Fi atau IP salah | Pastikan satu Wi-Fi dan gunakan IP yang muncul di terminal |

## Bukti yang Perlu Dikirim ke Developer

Jika diminta validasi jarak jauh, kirim:

1. Screenshot terminal setelah `./setup_raspberry_pi.sh`.
2. Screenshot terminal saat `./run_real_mode.sh` berjalan.
3. Screenshot halaman Pengukuran setelah klik **Ambil Hasil Pengukuran**.
4. Screenshot halaman Riwayat.
5. Jika gagal, screenshot pesan error yang muncul.

## Cara Menghentikan Website

Tekan `Ctrl+C` di terminal tempat website berjalan.

Nanti akan muncul pesan:

```text
Website UkurKu dihentikan.
```
