#!/bin/bash

# ============================================================
# Setup Script untuk Raspberry Pi - Sorting System UkurKu
# ============================================================

set -e

echo "=========================================="
echo "Setup Sorting System UkurKu di Raspberry Pi"
echo "=========================================="
echo ""

# Cek Python3
echo "[1/6] Memeriksa Python3..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 tidak ditemukan. Silakan install dengan:"
    echo "   sudo apt update && sudo apt install python3"
    exit 1
fi
PYTHON_VERSION=$(python3 --version)
echo "✓ $PYTHON_VERSION terdeteksi"
echo ""

# Cek pip3
echo "[2/6] Memeriksa pip3..."
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 tidak ditemukan. Silakan install dengan:"
    echo "   sudo apt update && sudo apt install python3-pip"
    exit 1
fi
PIP_VERSION=$(pip3 --version)
echo "✓ $PIP_VERSION terdeteksi"
echo ""

# Install dependencies
echo "[3/6] Menginstall dependencies dari requirements_pi.txt..."
if [ -f "requirements_pi.txt" ]; then
    if pip3 install --user -r requirements_pi.txt; then
        echo "✓ Dependencies berhasil diinstall dengan --user"
    else
        echo "⚠ Install dengan --user gagal, mencoba dengan --break-system-packages..."
        if pip3 install --break-system-packages -r requirements_pi.txt; then
            echo "✓ Dependencies berhasil diinstall dengan --break-system-packages"
        else
            echo "❌ Gagal menginstall dependencies"
            exit 1
        fi
    fi
else
    echo "❌ File requirements_pi.txt tidak ditemukan"
    exit 1
fi
echo ""

# Setup .env
echo "[4/6] Menyiapkan file .env..."
if [ -f ".env" ]; then
    echo "✓ File .env sudah ada, tidak akan ditimpa"
else
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✓ File .env dibuat dari .env.example"
        echo "⚠ Silakan edit .env untuk menyesuaikan konfigurasi"
    else
        echo "❌ File .env.example tidak ditemukan"
        exit 1
    fi
fi
echo ""

# Cek program-python directory
echo "[5/6] Memeriksa lokasi program-python..."
FOUND_PATH=""
if [ -d "../program-python" ]; then
    FOUND_PATH="$(cd ../program-python && pwd)"
    echo "✓ Direktori ../program-python ditemukan"
elif [ -d "$HOME/program-python" ]; then
    FOUND_PATH="$HOME/program-python"
    echo "✓ Direktori $HOME/program-python ditemukan"
else
    echo "⚠ Direktori program-python tidak ditemukan di:"
    echo "  - ../program-python"
    echo "  - $HOME/program-python"
    echo "  Pastikan untuk menyesuaikan PROGRAM_PYTHON_BASE di .env secara manual"
fi

if [ -n "$FOUND_PATH" ]; then
    echo "  Memperbarui PROGRAM_PYTHON_BASE di .env ke: $FOUND_PATH"
    sed -i "s|PROGRAM_PYTHON_BASE=.*|PROGRAM_PYTHON_BASE=$FOUND_PATH|g" .env
    echo "✓ File .env telah diperbarui"
fi
echo ""

# Set executable permission
echo "[6/6] Memberikan permission execute pada run_real_mode.sh..."
if [ -f "run_real_mode.sh" ]; then
    chmod +x run_real_mode.sh
    echo "✓ run_real_mode.sh sekarang executable"
else
    echo "⚠ File run_real_mode.sh tidak ditemukan"
fi
echo ""

echo "=========================================="
echo "✓ Setup selesai!"
echo "=========================================="
echo ""
echo "Langkah selanjutnya:"
echo "1. Edit file .env untuk menyesuaikan konfigurasi"
echo "2. Pastikan kalibrasi sudah tersedia di lokasi yang benar"
echo "3. Jalankan: ./run_real_mode.sh"
echo ""
