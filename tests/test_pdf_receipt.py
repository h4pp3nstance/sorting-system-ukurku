"""
Unit Tests for web/pdf_receipt.py (Fitur A - Resi PDF)
Laptop-safe: fpdf2 pure-Python, tidak butuh hardware.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.pdf_receipt import (
    build_receipt_pdf,
    format_indonesian_datetime,
    format_indonesian_price,
)


def _sample_package(**overrides):
    pkg = {
        "id": "20260531_120000_ab12",
        "timestamp": "2026-05-31T12:00:00",
        "dimensions": {"panjang": 10.12, "lebar": 8.46, "tinggi": 5.0},
        "weight": {"aktual": 523.5, "volumetrik": 120.0,
                   "chargeable": 523.5, "source": "actual"},
        "service_type": "REGULER",
        "price": 6000,
        "measurement_id": "integrated_20260531_120000_123456",
        "sender": {"nama": "Budi", "telepon": "0811", "alamat": "Jl. Mawar 1"},
        "recipient": {"nama": "Siti", "telepon": "0822", "alamat": "Jl. Melati 2"},
    }
    pkg.update(overrides)
    return pkg


class TestBuildReceiptPdf:
    def test_returns_bytes(self):
        result = build_receipt_pdf(_sample_package())
        assert isinstance(result, bytes)

    def test_starts_with_pdf_magic(self):
        result = build_receipt_pdf(_sample_package())
        assert result[:4] == b"%PDF"

    def test_non_trivial_size(self):
        result = build_receipt_pdf(_sample_package())
        assert len(result) > 500

    def test_works_without_sender_recipient(self):
        pkg = _sample_package()
        del pkg["sender"]
        del pkg["recipient"]
        result = build_receipt_pdf(pkg)
        assert result[:4] == b"%PDF"

    def test_works_without_measurement_id(self):
        pkg = _sample_package()
        del pkg["measurement_id"]
        result = build_receipt_pdf(pkg)
        assert result[:4] == b"%PDF"

    def test_handles_missing_numeric_fields(self):
        pkg = {
            "id": "1",
            "dimensions": {},
            "weight": {},
            "service_type": "KARGO",
            "price": 0,
        }
        result = build_receipt_pdf(pkg)
        assert result[:4] == b"%PDF"

    def test_rejects_non_dict(self):
        import pytest
        with pytest.raises(ValueError):
            build_receipt_pdf("not a dict")


class TestFormatters:
    def test_datetime_indonesian(self):
        assert format_indonesian_datetime("2026-05-31T12:05:00") == "31 Mei 2026, 12:05"

    def test_datetime_empty(self):
        assert format_indonesian_datetime("") == "-"

    def test_datetime_invalid_passthrough(self):
        assert format_indonesian_datetime("bukan-tanggal") == "bukan-tanggal"

    def test_price_thousand_separator(self):
        assert format_indonesian_price(6000) == "Rp 6.000"

    def test_price_zero(self):
        assert format_indonesian_price(0) == "Rp 0"

    def test_price_none(self):
        assert format_indonesian_price(None) == "Rp 0"
