"""
Validation Engine - bandingkan pengukuran Mitra vs MPC.

Pure function (tanpa Flask/hardware/IO) -> testable penuh di laptop.

Aturan status (sesuai PDF Keputusan Alur):
- Valid        : semua selisih dalam toleransi.
- Perlu Review : selisih dimensi atau berat aktual melewati toleransi,
                 TAPI berat tagihan masih dalam toleransi (ongkir tak terpengaruh).
- Tidak Sesuai : selisih berat tagihan melewati toleransi (memengaruhi ongkir).
"""

STATUS_VALID = "valid"
STATUS_PERLU_REVIEW = "perlu_review"
STATUS_TIDAK_SESUAI = "tidak_sesuai"

STATUS_LABELS = {
    STATUS_VALID: "Valid",
    STATUS_PERLU_REVIEW: "Perlu Review",
    STATUS_TIDAK_SESUAI: "Tidak Sesuai",
}

# Field yang dibandingkan -> (key pengukuran, key toleransi)
_DIMENSION_FIELDS = [
    ("panjang", "dimensi_cm"),
    ("lebar", "dimensi_cm"),
    ("tinggi", "dimensi_cm"),
]
_WEIGHT_ACTUAL_FIELD = ("berat_aktual", "berat_aktual_g")
_CHARGEABLE_FIELD = ("chargeable_weight", "berat_tagihan_g")


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _selisih(mitra, mpc, key):
    return abs(_to_float(mitra.get(key)) - _to_float(mpc.get(key)))


def normalize_dimensions(measurement):
    """Return copy of measurement dengan panjang/lebar/tinggi di-sort menurun.

    Orientasi berbeda (P/L/T tertukar) akan menghasilkan representasi yang sama
    sehingga perbandingan tidak memicu false breach karena orientasi.
    Field lain (berat_aktual, berat_volumetrik, chargeable_weight) tidak diubah.
    """
    m = dict(measurement) if measurement else {}
    dims = sorted(
        [_to_float(m.get("panjang")), _to_float(m.get("lebar")), _to_float(m.get("tinggi"))],
        reverse=True,
    )
    m["panjang"] = dims[0]
    m["lebar"] = dims[1]
    m["tinggi"] = dims[2]
    return m


def is_package_present(measurement, min_weight_g=10.0, min_dim_cm=0.5):
    """Deteksi apakah ada paket di alat ukur.

    Return False jika:
    - berat_aktual < min_weight_g, ATAU
    - salah satu dimensi (panjang/lebar/tinggi) < min_dim_cm.

    Berguna untuk mendeteksi "alat kosong / paket tidak terdeteksi".
    """
    m = measurement or {}
    if _to_float(m.get("berat_aktual")) < min_weight_g:
        return False
    for key, _ in _DIMENSION_FIELDS:
        if _to_float(m.get(key)) < min_dim_cm:
            return False
    return True


def compare_measurements(mitra, mpc, tolerances, normalize_orientation=False):
    """Bandingkan dua pengukuran dan tentukan status validasi.

    Args:
        mitra: dict pengukuran Mitra (panjang, lebar, tinggi,
               berat_aktual, berat_volumetrik, chargeable_weight).
        mpc: dict pengukuran MPC (key sama).
        tolerances: dict {dimensi_cm, berat_aktual_g, berat_tagihan_g}.
        normalize_orientation: jika True, sort dimensi P/L/T menurun pada
            kedua sisi sebelum membandingkan sehingga orientasi berbeda
            tidak memicu false breach. Default False (perilaku lama).

    Returns:
        dict {status, status_label, selisih: {...}, breaches: [...]}.
    """
    mitra = mitra or {}
    mpc = mpc or {}
    if normalize_orientation:
        mitra = normalize_dimensions(mitra)
        mpc = normalize_dimensions(mpc)
    tolerances = tolerances or {}

    tol_dim = _to_float(tolerances.get("dimensi_cm", 1.0))
    tol_aktual = _to_float(tolerances.get("berat_aktual_g", 50.0))
    tol_tagihan = _to_float(tolerances.get("berat_tagihan_g", 100.0))

    selisih = {}
    breaches = []

    # Dimensi
    dimensi_breach = False
    for key, _ in _DIMENSION_FIELDS:
        diff = _selisih(mitra, mpc, key)
        selisih[key] = round(diff, 3)
        if diff > tol_dim:
            dimensi_breach = True
            breaches.append(key)

    # Berat aktual
    aktual_key, _ = _WEIGHT_ACTUAL_FIELD
    diff_aktual = _selisih(mitra, mpc, aktual_key)
    selisih[aktual_key] = round(diff_aktual, 3)
    aktual_breach = diff_aktual > tol_aktual
    if aktual_breach:
        breaches.append(aktual_key)

    # Berat volumetrik (info saja, tidak mengubah status sendiri)
    diff_vol = _selisih(mitra, mpc, "berat_volumetrik")
    selisih["berat_volumetrik"] = round(diff_vol, 3)

    # Berat tagihan (chargeable) -> penentu "tidak sesuai"
    charge_key, _ = _CHARGEABLE_FIELD
    diff_charge = _selisih(mitra, mpc, charge_key)
    selisih[charge_key] = round(diff_charge, 3)
    charge_breach = diff_charge > tol_tagihan
    if charge_breach:
        breaches.append(charge_key)

    if charge_breach:
        status = STATUS_TIDAK_SESUAI
    elif dimensi_breach or aktual_breach:
        status = STATUS_PERLU_REVIEW
    else:
        status = STATUS_VALID

    return {
        "status": status,
        "status_label": STATUS_LABELS[status],
        "selisih": selisih,
        "breaches": breaches,
        "tolerances_used": {
            "dimensi_cm": tol_dim,
            "berat_aktual_g": tol_aktual,
            "berat_tagihan_g": tol_tagihan,
        },
    }


def extract_measurement(package):
    """Ambil flat measurement dict dari envelope package (untuk sisi Mitra)."""
    package = package or {}
    dims = package.get("dimensions", {}) or {}
    weight = package.get("weight", {}) or {}
    return {
        "panjang": _to_float(dims.get("panjang")),
        "lebar": _to_float(dims.get("lebar")),
        "tinggi": _to_float(dims.get("tinggi")),
        "berat_aktual": _to_float(weight.get("aktual")),
        "berat_volumetrik": _to_float(weight.get("volumetrik")),
        "chargeable_weight": _to_float(weight.get("chargeable")),
    }
