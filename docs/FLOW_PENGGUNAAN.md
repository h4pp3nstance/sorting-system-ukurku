# Flow Penggunaan Sistem UkurKu

Dokumen ini menjelaskan langkah-demi-langkah cara pakai sistem untuk dua peran:

- **Mitra** — menimbang & mengukur paket lalu mencetak resi.
- **MPC** (Mitra Pusat Cabang) — memvalidasi pengukuran Mitra dengan mengukur ulang.

> **Catatan istilah:**
> - **PB Start** = push button (tombol fisik) berlampu hijau di alat. Saat ditekan, tahap17 mendeteksi & meluncurkan tahap18 (program pengukuran).
> - **Tahap 18** = program CLI yang membaca kamera + loadcell + sensor ultrasonik, lalu menulis hasil ke `hasil_tahap18/latest_integrated_chargeable.json`.
> - **Lampu kuning** = indikator standby di PB. Lampu hijau menyala saat PB Start ditekan / mode RUN aktif.

---

## A. Flow Mitra (Pengukuran + Cetak Resi)

### Persiapan (sekali per sesi)

1. **MCB ON** di panel listrik alat.
2. Tunggu sistem standby — **lampu kuning di PB menyala** (sistem siap, tahap18 belum berjalan).
3. Di laptop/HP, buka dashboard:
   - LAN: `http://192.168.151.48:5000`
   - Tailscale: `http://100.106.117.82:5000`
4. **Login Mitra** dengan akun mitra (default test: `mitra` / `mitra123`).
5. Dashboard otomatis terbuka di halaman pengukuran utama.

### Setiap paket — urutan WAJIB

> **PENTING**: Isi form **SEBELUM** tekan PB Start. Kalau tidak, paket akan tersimpan tanpa data pengirim/penerima dan resi akan kosong di bagian itu (harus di-backfill manual).

6. **Isi form Pengirim & Penerima di dashboard:**
   - Pengirim → Nama (wajib), Telepon, Alamat
   - Penerima → Nama (wajib), Telepon, Alamat
   - Tunggu indikator **"Tersimpan"** muncul di samping form (auto-save 0,5 detik setelah berhenti mengetik).
   - Form draft berlaku selama 5 menit. Kalau lewat tanpa PB Start, draft hangus → harus isi lagi.

7. **Letakkan paket** di atas alat (di area pengukuran kamera + loadcell).

8. **Tekan PB Start (tombol hijau)** di alat.
   - Lampu hijau menyala.
   - Tahap 17 launch Tahap 18.
   - **Preview kamera di dashboard otomatis menyala** (delay ~3 detik karena polling).

9. **Paket diukur otomatis** oleh tahap18 (dimensi + berat).

10. **Hasil pengukuran muncul real-time di dashboard:**
    - Kartu paket baru muncul di list (sender/recipient ter-attach dari form draft).
    - Notifikasi/highlight di kolom riwayat.

11. **Klik tombol "Cetak Resi" atau "Download PDF"** pada paket tersebut.
    - Resi menampilkan: No. Paket, Tanggal, ID Ukur, Dimensi, Berat, Layanan, **Pengirim, Penerima**.

12. **(Opsional) Letakkan paket baru** dan ulangi step 6-11 dengan data pengirim/penerima baru.

### Selesai sesi

13. **Logout Mitra** (menu pojok kanan atas → Keluar).
    - Backend kirim sinyal `SIGINT` ke tahap18 → tahap18 berhenti rapi (kamera + servo + GPIO di-cleanup).
    - **Preview kamera di dashboard otomatis mati** (delay ~3 detik).
    - **Lampu hijau mati, lampu kuning kembali menyala** (sistem standby).

14. **(Opsional) MCB OFF** kalau sesi alat tutup.

### Lupa isi form sebelum PB? Backfill paket existing

Kalau paket sudah masuk tanpa sender/recipient (misal lupa isi form atau test cepat):

1. Di dashboard, cari paket di kolom "Riwayat" atau tab History.
2. Klik tombol **"Lengkapi Data"** pada paket tersebut.
3. Modal terbuka — isi Pengirim & Penerima.
4. Klik **Simpan**.
5. Cetak ulang resi → sender/recipient sudah ada.

---

## B. Flow MPC (Validasi Pengukuran Mitra)

### Persiapan

1. Sistem sudah standby (lampu kuning menyala). Tahap18 OFF.
2. Di dashboard, **Login MPC** (default test: `mpc` / `mpc123`).
3. Dashboard MPC tampil — daftar paket yang sudah diukur Mitra dan menunggu validasi.

### Setiap paket — urutan

4. **Buka menu Validasi** (atau langsung di halaman utama MPC, daftar paket masuk).

5. **Pilih paket** yang akan divalidasi (klik baris paket di tabel).

6. Halaman validasi paket terbuka → menampilkan data pengukuran Mitra (P×L×T + berat).

7. **Klik tombol "Ukur Paket (Mode MPC)"**.
   - Backend set **ARM state** (paket di-arm untuk re-measure).
   - Banner muncul: "Paket [ID] sedang menunggu PB Start (sisa 5 menit)".
   - Countdown 5 menit mulai berjalan.

8. **Letakkan paket** yang sama di alat.

9. **Tekan PB Start (tombol hijau)** di alat.
   - Tahap 18 berjalan dalam **mode MPC** (otomatis di-route ke validation attempt, BUKAN paket baru).
   - **Preview kamera di halaman validasi otomatis menyala** (sudah auto-start sejak halaman dibuka).

10. **Paket diukur ulang** oleh tahap18.

11. **Hasil pengukuran MPC tampil real-time:**
    - P×L×T dan berat MPC ditampilkan di samping pengukuran Mitra.
    - **Status validasi muncul otomatis:**
      - ✅ **Valid** — selisih dalam toleransi (default 1.0 cm + 50 g)
      - ⚠️ **Perlu Review** — dimensi atau berat aktual di luar toleransi (tapi tarif tidak berubah)
      - ❌ **Tidak Sesuai** — berat tagihan beda → tarif harus revisi
    - Selisih (delta) per axis & per berat ditampilkan.

12. **(Opsional) Ukur ulang lagi** kalau status "Perlu Review" / "Tidak Sesuai" dan MPC ingin verifikasi:
    - Klik "Ukur Paket (Mode MPC)" lagi → ARM state baru.
    - Tekan PB Start → hasil baru ditambahkan ke **riwayat attempt** (tidak menimpa).
    - Semua attempt tersimpan untuk audit trail (1×, 2×, 3× dst).

13. **Status final** = status dari attempt terakhir. Notifikasi otomatis terkirim ke Mitra (untuk status Perlu Review / Tidak Sesuai).

### Selesai sesi MPC

14. **MPC Logout**.
    - `SIGINT` ke tahap18 → berhenti.
    - **Preview kamera mati, lampu kuning kembali menyala** (standby).

---

## C. Aturan Penting (Common Pitfalls)

### Mitra

- ❌ **Jangan tekan PB Start sebelum isi form** → paket masuk tanpa sender/recipient. Solusi: pakai modal "Lengkapi Data".
- ❌ **Jangan logout di tengah pengukuran** → tahap18 ke-SIGINT mendadak. Tunggu paket muncul di dashboard dulu.
- ✅ **Form draft berlaku 5 menit** — kalau menumpuk paket banyak, ulangi isi form per paket (cepat karena indicator "Tersimpan" instan).
- ✅ **Satu form draft = satu paket**. Begitu PB Start memicu paket masuk, draft otomatis terkonsumsi (kosong lagi untuk paket berikutnya).

### MPC

- ❌ **Jangan klik "Ukur Paket (Mode MPC)" untuk dua paket berbeda sekaligus** → ARM state single-slot, paket kedua akan tertolak (409 Conflict) sampai paket pertama selesai atau dibatalkan.
- ❌ **Jangan tekan PB Start kalau MPC belum klik "Ukur Paket (Mode MPC)"** → paket akan diperlakukan sebagai paket Mitra baru (bukan validasi).
- ✅ **ARM state expire 5 menit** kalau MPC klik "Ukur" tapi tidak tekan PB Start dalam 5 menit. Klik lagi untuk re-arm.
- ✅ **Bisa cancel ARM** sebelum PB Start lewat tombol "Batalkan Ukur" di banner.

### Alat (Hardware)

- ✅ **Lampu kuning = standby (siap).**
- ✅ **Lampu hijau = sedang mengukur (tahap18 jalan).**
- ❌ **Lampu merah = emergency / error.** Sistem otomatis stop. Cek log + restart.
- ❌ **Jangan switch akun (logout-login) di tengah tahap18 jalan** → tahap18 ter-stop (by design, untuk keamanan kamera/servo).

---

## D. Troubleshooting Cepat

| Gejala | Kemungkinan | Aksi |
|--------|-------------|------|
| Paket masuk tanpa sender/recipient di resi | Form tidak diisi sebelum PB | Klik "Lengkapi Data" di list paket |
| Form draft "Gagal simpan" | Session expired / network | Refresh dashboard, login ulang |
| Preview kamera tidak nyala saat PB Start | tahap18 belum detected / polling delay | Tunggu 3 detik. Kalau tetap tidak nyala, klik manual "Mulai Preview" |
| Preview "Kamera sedang dipakai proses lain" | tahap18 + web rebutan kamera | Logout & login ulang, atau tunggu tahap18 selesai |
| MPC klik "Ukur Paket" gagal (409 Conflict) | Ada paket lain yang masih di-arm | Tunggu ARM expire (max 5 menit) atau cancel manual |
| Notifikasi MPC tidak sampai ke Mitra | Mitra belum login / SSE terputus | Mitra refresh dashboard |
| Resi tidak menampilkan section Pengirim | Data sender memang null di DB | Backfill via "Lengkapi Data" → cetak ulang |

---

## E. Daftar Fitur per Role

| Fitur | Mitra | MPC | Admin |
|-------|:-----:|:---:|:-----:|
| Dashboard pengukuran | ✅ | ❌ | ✅ |
| Form draft auto-save | ✅ | ❌ | ✅ |
| Modal "Lengkapi Data" | ✅ | ❌ | ✅ |
| Cetak resi PDF | ✅ | ❌ | ✅ |
| Dashboard MPC + Validasi | ❌ | ✅ | ✅ |
| Klik "Ukur Paket Mode MPC" (ARM) | ❌ | ✅ | ✅ |
| Lihat riwayat attempt validasi | ❌ | ✅ | ✅ |
| Atur toleransi validasi | ❌ | ❌ | ✅ |
| Kelola akun mitra | ❌ | ❌ | ✅ |
| Lihat semua paket (history) | ✅ (sendiri) | ✅ (semua) | ✅ (semua) |
