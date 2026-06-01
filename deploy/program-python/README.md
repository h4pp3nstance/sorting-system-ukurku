# deploy/program-python

File di sini adalah **glue integrasi** yang ditulis untuk menghubungkan web
dashboard (`sorting-system-ukurku`) dengan kode pengukuran Raspberry Pi
(`program-python`). Disimpan di repo ini supaya ter-version-control dan tidak
hilang — folder `program-python` di Pi TIDAK punya git sendiri.

## `tahap14_session.py`

Wrapper "kamera hangat" untuk mode `MEASUREMENT_MODE=in_process`:
- `MeasurementSession.__init__` — init GPIO/loadcell/kamera + load kalibrasi sekali.
- `measure_once()` — satu pengukuran headless (tanpa window/`input()`/loop tak terbatas).
- `retare()` / `close()`.

Me-reuse fungsi dari `tahap14_integrated_chargeable.py` + `tahap10_*` (TIDAK
menyalin logika hitung). Pasangannya di sisi web: `web/measurement_engine.py`.

## Cara deploy ke Pi

Salin file ini ke folder `program-python` di Pi (sejajar dengan
`tahap14_integrated_chargeable.py`):

```bash
cp deploy/program-python/tahap14_session.py <path>/program-python/
```

Lalu set `MEASUREMENT_MODE=in_process` di `.env` web.

## Catatan provenance

`program-python` di Pi adalah versi KANONIK (lebih baru — sudah ada servo
pendorong / tahap15). Jika nanti `program-python` diberi git repo sendiri,
`tahap14_session.py` sebaiknya pindah ke sana sebagai sumber utama, dan
salinan di sini dihapus untuk menghindari divergensi.

Terverifikasi jalan di Pi (2026-06-01): `/api/measure` mode in_process
menghasilkan pengukuran live, kamera hangat (klik ke-2 ~2s vs ~9s cold start),
hasil tersimpan ke SQLite.
