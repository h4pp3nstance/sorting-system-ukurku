#!/bin/bash
# ============================================================
# JALANKAN WEBSITE UKURKU - MODE ALAT
# ============================================================
# Script untuk menjalankan website di Raspberry Pi yang sama dengan alat ukur.

set -e

# Trap Ctrl+C untuk pesan keluar yang bersih
trap 'echo -e "\nWebsite UkurKu dihentikan."; exit 0' SIGINT

echo "============================================================"
echo "  WEBSITE UKURKU - MODE ALAT"
echo "============================================================"
echo ""

# ------------------------------------------------------------
# Cek dependensi Python
# ------------------------------------------------------------
echo "Memeriksa dependensi Python..."
if ! command -v python3 &> /dev/null; then
    echo "❌ python3 tidak ditemukan."
    echo "Silakan install Python 3 terlebih dahulu."
    exit 1
fi

if ! python3 -c "import flask" 2>/dev/null; then
    echo "❌ Flask belum terinstall."
    echo "Jalankan setup terlebih dahulu: ./setup_raspberry_pi.sh"
    exit 1
fi

# ------------------------------------------------------------
# Cek file .env
# ------------------------------------------------------------
echo "Memeriksa konfigurasi..."
if [ ! -f .env ]; then
    echo "❌ File .env tidak ditemukan."
    echo "Jalankan setup terlebih dahulu: ./setup_raspberry_pi.sh"
    exit 1
fi

# ------------------------------------------------------------
# Dapatkan alamat IP lokal
# ------------------------------------------------------------
echo "Mencari alamat IP..."
IP_ADDR=$(hostname -I 2>/dev/null | awk '{print $1}')

echo ""
echo "Website akan dijalankan."
echo ""
echo "Buka alamat berikut dari Raspberry Pi:"
echo "  http://localhost:5000"
if [ -n "$IP_ADDR" ]; then
    echo ""
    echo "Atau dari HP/laptop yang satu Wi-Fi:"
    echo "  http://$IP_ADDR:5000"
fi
echo ""
echo "Tekan Ctrl+C untuk menghentikan website."
echo "============================================================"
echo ""

# ------------------------------------------------------------
# Jalankan web server
# ------------------------------------------------------------
python3 run_web.py
