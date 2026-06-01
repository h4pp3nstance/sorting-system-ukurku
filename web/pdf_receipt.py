"""
PDF Receipt Generator (fpdf2, pure-Python, Pi-ARM friendly)

build_receipt_pdf(package, ...) -> bytes
Membuat resi PDF lebar 80mm dari data paket yang sudah tersimpan.
Pure function (tanpa hardware/Flask) supaya bisa diuji penuh di laptop.
"""

from datetime import datetime

from fpdf import FPDF


RECEIPT_WIDTH_MM = 80
RECEIPT_HEIGHT_MM = 250

_INDONESIAN_MONTHS = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


def format_indonesian_datetime(iso_string):
    """Format ISO timestamp jadi '21 Mei 2026, 14:32' (Indonesian)."""
    if not iso_string:
        return "-"
    try:
        dt = datetime.fromisoformat(str(iso_string))
    except (ValueError, TypeError):
        return str(iso_string)
    month_name = _INDONESIAN_MONTHS[dt.month - 1]
    return f"{dt.day} {month_name} {dt.year}, {dt.hour:02d}:{dt.minute:02d}"


def format_indonesian_price(price):
    """Format harga jadi 'Rp 6.000' dengan pemisah ribuan Indonesia."""
    try:
        amount = float(price or 0)
    except (TypeError, ValueError):
        amount = 0
    return "Rp {:,.0f}".format(amount).replace(",", ".")


def _display_id(package):
    return "PKT-" + str(package.get("id", "")).zfill(5)


def _safe_num(value, fmt="{:.1f}"):
    try:
        return fmt.format(float(value))
    except (TypeError, ValueError):
        return "-"


class _ReceiptPDF(FPDF):
    """FPDF 80mm tanpa header/footer otomatis (resi kustom)."""

    def __init__(self):
        super().__init__(
            orientation="P",
            unit="mm",
            format=(RECEIPT_WIDTH_MM, RECEIPT_HEIGHT_MM),
        )
        self.set_auto_page_break(auto=True, margin=5)
        self.set_margins(left=4, top=5, right=4)


def _divider(pdf):
    pdf.ln(1)
    y = pdf.get_y()
    pdf.set_draw_color(150, 150, 150)
    pdf.dashed_line(4, y, RECEIPT_WIDTH_MM - 4, y, dash_length=1, space_length=1)
    pdf.ln(2)


def _section_title(pdf, text):
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(0, 4, text, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(0.5)


def _kv_row(pdf, label, value):
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(20, 4, label, new_x="RIGHT", new_y="TOP")
    pdf.set_font("Helvetica", "B", 8)
    pdf.multi_cell(0, 4, str(value), align="R", new_x="LMARGIN", new_y="NEXT")


def _party_block(pdf, title, party):
    if not party:
        return
    _section_title(pdf, title)
    nama = party.get("nama") or "-"
    telepon = party.get("telepon")
    alamat = party.get("alamat")
    pdf.set_font("Helvetica", "B", 8)
    pdf.multi_cell(0, 4, nama, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8)
    if telepon:
        pdf.multi_cell(0, 4, str(telepon), new_x="LMARGIN", new_y="NEXT")
    if alamat:
        pdf.multi_cell(0, 4, str(alamat), new_x="LMARGIN", new_y="NEXT")


def build_receipt_pdf(package, printed_at_iso=None):
    """Bangun resi PDF dari dict package, kembalikan bytes.

    package: dict dengan field dimensions/weight/service_type/price,
    opsional sender/recipient/measurement_id/timestamp/id.
    """
    if not isinstance(package, dict):
        raise ValueError("package harus berupa dict")

    dimensions = package.get("dimensions", {}) or {}
    weight = package.get("weight", {}) or {}

    pdf = _ReceiptPDF()
    pdf.add_page()

    # Header
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 6, "UKURKU", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 4, "Resi Pengukuran Paket", align="C",
             new_x="LMARGIN", new_y="NEXT")

    _divider(pdf)

    _kv_row(pdf, "No. Paket", _display_id(package))
    _kv_row(pdf, "Tanggal", format_indonesian_datetime(package.get("timestamp")))
    if package.get("measurement_id"):
        _kv_row(pdf, "ID Ukur", package.get("measurement_id"))

    if package.get("sender"):
        _divider(pdf)
        _party_block(pdf, "PENGIRIM", package.get("sender"))

    if package.get("recipient"):
        _divider(pdf)
        _party_block(pdf, "PENERIMA", package.get("recipient"))

    _divider(pdf)
    _section_title(pdf, "DIMENSI")
    _kv_row(pdf, "Panjang", _safe_num(dimensions.get("panjang"), "{:.2f}") + " cm")
    _kv_row(pdf, "Lebar", _safe_num(dimensions.get("lebar"), "{:.2f}") + " cm")
    _kv_row(pdf, "Tinggi", _safe_num(dimensions.get("tinggi"), "{:.2f}") + " cm")

    _divider(pdf)
    _section_title(pdf, "BERAT")
    _kv_row(pdf, "Aktual", _safe_num(weight.get("aktual")) + " g")
    _kv_row(pdf, "Volumetrik", _safe_num(weight.get("volumetrik")) + " g")
    _kv_row(pdf, "Tagihan", _safe_num(weight.get("chargeable")) + " g")
    if weight.get("source"):
        _kv_row(pdf, "Sumber", str(weight.get("source")))

    _divider(pdf)
    _section_title(pdf, "LAYANAN")
    _kv_row(pdf, "Jenis", str(package.get("service_type", "-")))

    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "Biaya: " + format_indonesian_price(package.get("price")),
             align="C", new_x="LMARGIN", new_y="NEXT")

    _divider(pdf)
    pdf.set_font("Helvetica", "", 7)
    printed = format_indonesian_datetime(
        printed_at_iso or datetime.now().isoformat()
    )
    pdf.cell(0, 4, "Dicetak: " + printed, align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 4, "Terima kasih", align="C",
             new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())
