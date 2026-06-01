"""
Flask Routes
Main pages and API endpoints for Sorting System
With SQLite storage, real-time updates (SSE), and logging
"""

from flask import Blueprint, render_template, jsonify, request, Response, redirect, url_for, flash
from datetime import datetime
import json
import queue
import threading

from web.measurement_bridge import (
    should_use_file_bridge, get_measurement_from_file,
    classify_package, MeasurementBridgeError
)
from web.mode_helper import get_system_mode_info
from web.auth import (
    role_required, api_login_required, api_role_required, current_user,
    ROLE_MITRA, ROLE_MPC, ROLE_ADMIN,
)

_MODE_INFO = get_system_mode_info()

# Import logger
try:
    from core.logger import get_logger
    log = get_logger()
except ImportError:
    # Fallback if logger not available
    class DummyLogger:
        def info(self, msg, **kw): print(f"[INFO] {msg}")
        def error(self, msg, **kw): print(f"[ERROR] {msg}")
        def warning(self, msg, **kw): print(f"[WARNING] {msg}")
        def operation(self, msg, **kw): print(f"[OPERATION] {msg}")
        def audit(self, msg, **kw): print(f"[AUDIT] {msg}")
    log = DummyLogger()

# Create blueprints
main_bp = Blueprint('main', __name__)
api_bp = Blueprint('api', __name__)

# =============================================================================
# Storage Backend (SQLite default, in-memory fallback)
# =============================================================================

# Event queue for SSE (Server-Sent Events)
_event_queues = []
_event_lock = threading.Lock()

_storage = None
_storage_backend = "memory"

def get_storage():
    """Get or initialize storage backend.

    Default: SQLite (offline-first). Override via STORAGE_MODE env
    (sqlite|memory). Falls back to in-memory on any init error.
    """
    global _storage, _storage_backend

    if _storage is None:
        import os
        mode = os.getenv("STORAGE_MODE", "sqlite").lower()
        try:
            from storage.factory import create_storage_handler
            if mode == "sqlite":
                db_path = os.getenv("DB_PATH") or None
                _storage = create_storage_handler("sqlite", db_path=db_path)
            else:
                _storage = create_storage_handler(mode)
            _storage.connect()
            _storage_backend = mode
            log.info("Storage initialized", backend=mode)
        except Exception as e:
            log.warning("Storage init failed, using in-memory", error=str(e))
            _storage = InMemoryStorage()
            _storage_backend = "memory"

    return _storage


class InMemoryStorage:
    """Fallback in-memory storage if SQLite not available"""
    
    def __init__(self):
        self.packages = []
        self._next_id = 1
    
    def save_package(self, package_data):
        package_id = self._next_id
        self._next_id += 1
        
        package = {
            'id': package_id,
            'timestamp': datetime.now().isoformat(),
            **package_data
        }
        self.packages.append(package)
        return str(package_id)
    
    def get_package(self, package_id):
        for p in self.packages:
            if str(p['id']) == str(package_id):
                return p
        return None
    
    def get_all_packages(self, limit=100):
        return self.packages[-limit:][::-1]  # Newest first
    
    def get_statistics(self):
        total = len(self.packages)
        revenue = sum(p.get('price', 0) for p in self.packages)
        
        by_type = {
            'REGULER': {'count': 0, 'revenue': 0},
            'EXPRESS': {'count': 0, 'revenue': 0},
            'KARGO': {'count': 0, 'revenue': 0}
        }
        
        for p in self.packages:
            stype = p.get('service_type', 'UNKNOWN')
            if stype in by_type:
                by_type[stype]['count'] += 1
                by_type[stype]['revenue'] += p.get('price', 0)
        
        return {
            'total_packages': total,
            'total_revenue': revenue,
            'by_service_type': by_type
        }
    
    def reset_data(self):
        self.packages = []
        self._next_id = 1
        return True


# System status (always in-memory for runtime state)
system_status = {
    'mode': _MODE_INFO['mode_id'],
    'mode_info': _MODE_INFO,
    'is_running': False,
    'last_package': None,
    'total_today': {
        'REGULER': 0,
        'EXPRESS': 0,
        'KARGO': 0
    }
}


# =============================================================================
# Main Page Routes
# =============================================================================

def _scope_packages(packages):
    """Filter packages to the current Mitra's own data.

    Mitra users see only packages tagged with their mitra_id. Admin/MPC or
    sessions without a mitra_id (e.g. tests) see everything unchanged.
    """
    user = current_user()
    if not user or user.get('role') != ROLE_MITRA:
        return packages
    mitra_id = user.get('mitra_id')
    if not mitra_id:
        return packages
    return [p for p in packages if p.get('mitra_id') == mitra_id]


def _get_scoped_package(package_id):
    """Fetch a package only if the current user is allowed to see it.

    Mitra users can only access packages tagged with their own mitra_id.
    Admin/MPC or sessions without a mitra_id get the package unchanged.
    Returns None if not found OR not owned by the requesting Mitra (IDOR guard).
    """
    package = get_storage().get_package(package_id)
    if not package:
        return None
    user = current_user()
    if not user or user.get('role') != ROLE_MITRA:
        return package
    mitra_id = user.get('mitra_id')
    if not mitra_id:
        return package
    if package.get('mitra_id') != mitra_id:
        return None
    return package


@main_bp.route('/')
def landing():
    """Public landing page with role selection."""
    return render_template('landing.html',
                          mode_info=_MODE_INFO)


@main_bp.route('/dashboard')
@role_required(ROLE_MITRA)
def dashboard():
    """Main monitoring dashboard (Mitra)"""
    storage = get_storage()
    packages = _scope_packages(storage.get_all_packages(100))[:10]
    
    return render_template('dashboard.html',
                          status=system_status,
                          history=packages)


@main_bp.route('/peringatan')
@role_required(ROLE_MITRA)
def mitra_notifications():
    """Daftar peringatan dari MPC untuk Mitra ini."""
    from web import mpc_store
    user = current_user() or {}
    mitra_id = user.get('mitra_id')
    notifications = mpc_store.list_notifications(to_mitra_id=mitra_id)
    return render_template('peringatan.html',
                          status=system_status,
                          notifications=notifications)


@api_bp.route('/notifications/read', methods=['POST'])
@api_login_required
def api_notification_read():
    """Tandai sebuah peringatan sudah dibaca."""
    from web import mpc_store
    payload = request.get_json(silent=True) or {}
    try:
        notif_id = int(payload.get('id'))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'ID tidak valid.'}), 422
    ok = mpc_store.mark_read(notif_id)
    return jsonify({'success': ok})


@main_bp.route('/mpc')
@role_required(ROLE_MPC)
def mpc_dashboard():
    """MPC validation dashboard: paket masuk, statistik, peringatan."""
    from web import mpc_store
    storage = get_storage()
    packages = storage.get_all_packages(100)
    validations = {v['package_id']: v for v in mpc_store.list_validations()}
    return render_template('mpc.html',
                          status=system_status,
                          packages=packages,
                          validations=validations,
                          val_stats=mpc_store.validation_stats(),
                          notifications=mpc_store.list_notifications())


@main_bp.route('/mpc/validate/<package_id>')
@role_required(ROLE_MPC)
def mpc_validate_page(package_id):
    """Halaman validasi: tampilkan data Mitra + form ukur ulang MPC."""
    from web import mpc_store
    from web.validation_engine import extract_measurement
    storage = get_storage()
    package = storage.get_package(package_id)
    if not package:
        flash('Paket tidak ditemukan.', 'error')
        return redirect(url_for('main.mpc_dashboard'))

    return render_template('validate.html',
                          status=system_status,
                          package=package,
                          mitra_measurement=extract_measurement(package),
                          existing=mpc_store.get_validation(package_id))


@api_bp.route('/mpc/validate', methods=['POST'])
@api_login_required
def api_mpc_validate():
    """Proses input ukur ulang MPC -> bandingkan -> simpan + notifikasi."""
    from web import mpc_store
    from web.validation_engine import (
        compare_measurements, extract_measurement,
        STATUS_TIDAK_SESUAI, STATUS_PERLU_REVIEW,
    )
    from web.settings_store import get_tolerances

    payload = request.get_json(silent=True) or {}
    package_id = payload.get('package_id')

    storage = get_storage()
    package = storage.get_package(package_id) if package_id else None
    if not package:
        return jsonify({'success': False,
                        'error': 'Paket tidak ditemukan.'}), 404

    def _num(key):
        try:
            return float(payload.get(key) or 0)
        except (TypeError, ValueError):
            return 0.0

    panjang = _num('panjang')
    lebar = _num('lebar')
    tinggi = _num('tinggi')
    berat_aktual = _num('berat_aktual')
    if panjang <= 0 or lebar <= 0 or tinggi <= 0 or berat_aktual <= 0:
        return jsonify({'success': False,
                        'error': 'Dimensi dan berat MPC harus lebih dari 0.'}), 422

    berat_volumetrik = round((panjang * lebar * tinggi) / 6000 * 1000, 1)
    chargeable = max(berat_aktual, berat_volumetrik)
    mpc_measurement = {
        'panjang': panjang, 'lebar': lebar, 'tinggi': tinggi,
        'berat_aktual': berat_aktual, 'berat_volumetrik': berat_volumetrik,
        'chargeable_weight': chargeable,
    }

    mitra_measurement = extract_measurement(package)
    result = compare_measurements(mitra_measurement, mpc_measurement,
                                  get_tolerances())

    user = current_user() or {}
    mpc_store.save_validation(
        package_id, mpc_measurement, result,
        mpc_username=user.get('username'),
        catatan=payload.get('catatan'),
    )

    if result['status'] in (STATUS_TIDAK_SESUAI, STATUS_PERLU_REVIEW):
        mpc_store.create_notification(
            package_id=package_id,
            to_mitra_id=package.get('mitra_id'),
            title='Validasi: ' + result['status_label'],
            message='Paket #{} dinyatakan {} oleh MPC.'.format(
                package_id, result['status_label']),
            status=result['status'],
        )

    return jsonify({'success': True, 'data': {
        'status': result['status'],
        'status_label': result['status_label'],
        'selisih': result['selisih'],
        'breaches': result['breaches'],
        'mpc_measurement': mpc_measurement,
    }})


@main_bp.route('/history/export.csv')
@role_required(ROLE_MITRA)
def history_export_csv():
    """Export riwayat paket (Mitra-scoped) sebagai file CSV."""
    import csv
    import io

    storage = get_storage()
    packages = _scope_packages(storage.get_all_packages(1000))

    service_type = request.args.get('type')
    if service_type:
        packages = [p for p in packages
                    if p.get('service_type') == service_type]

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        'ID', 'Waktu', 'Panjang_cm', 'Lebar_cm', 'Tinggi_cm',
        'Berat_Aktual_g', 'Berat_Volumetrik_g', 'Chargeable_g',
        'Layanan', 'Biaya_Rp',
    ])
    for p in packages:
        dims = p.get('dimensions', {}) or {}
        weight = p.get('weight', {}) or {}
        writer.writerow([
            p.get('id', ''),
            p.get('timestamp', ''),
            dims.get('panjang', ''),
            dims.get('lebar', ''),
            dims.get('tinggi', ''),
            weight.get('aktual', ''),
            weight.get('volumetrik', ''),
            weight.get('chargeable', ''),
            p.get('service_type', ''),
            p.get('price', ''),
        ])

    filename = 'riwayat-paket-' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.csv'
    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': 'attachment; filename="' + filename + '"'
        }
    )


@main_bp.route('/admin')
@role_required(ROLE_ADMIN)
def admin_dashboard():
    """Admin management dashboard (placeholder, Phase 1)."""
    storage = get_storage()
    stats = storage.get_statistics()
    from web.auth import list_users
    from web.settings_store import load_settings
    users = list_users()
    return render_template('admin.html',
                          status=system_status,
                          stats=stats,
                          users=users,
                          user_count=len(users),
                          settings=load_settings(),
                          all_packages=storage.get_all_packages(100))


@main_bp.route('/admin/users/create', methods=['POST'])
@role_required(ROLE_ADMIN)
def admin_user_create():
    from web.auth import create_user
    ok, err = create_user(
        username=request.form.get('username'),
        password=request.form.get('password'),
        role=request.form.get('role'),
        name=request.form.get('name'),
        mitra_id=request.form.get('mitra_id'),
        mpc_id=request.form.get('mpc_id'),
    )
    flash('User berhasil ditambahkan.' if ok else err,
          'success' if ok else 'error')
    return redirect(url_for('main.admin_dashboard'))


@main_bp.route('/admin/users/update', methods=['POST'])
@role_required(ROLE_ADMIN)
def admin_user_update():
    from web.auth import update_user
    ok, err = update_user(
        username=request.form.get('username'),
        name=request.form.get('name'),
        role=request.form.get('role'),
        password=request.form.get('password') or None,
        mitra_id=request.form.get('mitra_id'),
        mpc_id=request.form.get('mpc_id'),
    )
    flash('User berhasil diperbarui.' if ok else err,
          'success' if ok else 'error')
    return redirect(url_for('main.admin_dashboard'))


@main_bp.route('/admin/users/delete', methods=['POST'])
@role_required(ROLE_ADMIN)
def admin_user_delete():
    from web.auth import delete_user, current_user
    acting = (current_user() or {}).get('username')
    ok, err = delete_user(request.form.get('username'), acting_username=acting)
    flash('User berhasil dihapus.' if ok else err,
          'success' if ok else 'error')
    return redirect(url_for('main.admin_dashboard'))


@main_bp.route('/admin/settings', methods=['POST'])
@role_required(ROLE_ADMIN)
def admin_settings_update():
    from web.settings_store import update_tolerances, update_tariffs
    section = request.form.get('section')
    if section == 'toleransi':
        update_tolerances(
            dimensi_cm=request.form.get('dimensi_cm'),
            berat_aktual_g=request.form.get('berat_aktual_g'),
            berat_tagihan_g=request.form.get('berat_tagihan_g'),
        )
        flash('Toleransi validasi disimpan.', 'success')
    elif section == 'tarif':
        update_tariffs(
            reguler=request.form.get('reguler'),
            express=request.form.get('express'),
            kargo=request.form.get('kargo'),
        )
        flash('Tarif layanan disimpan.', 'success')
    else:
        flash('Bagian pengaturan tidak dikenali.', 'error')
    return redirect(url_for('main.admin_dashboard'))


@main_bp.route('/history')
@role_required(ROLE_MITRA)
def history():
    """Package history page"""
    storage = get_storage()
    packages = _scope_packages(storage.get_all_packages(200))[:100]
    
    return render_template('history.html',
                          packages=packages,
                          status=system_status)


# Indonesian month names for receipt formatting
_INDONESIAN_MONTHS = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember"
]


def _format_indonesian_datetime(iso_string):
    """Format ISO timestamp as '21 Mei 2026, 14:32' (Indonesian)."""
    if not iso_string:
        return "-"
    try:
        dt = datetime.fromisoformat(iso_string)
    except (ValueError, TypeError):
        return str(iso_string)
    month_name = _INDONESIAN_MONTHS[dt.month - 1]
    return f"{dt.day} {month_name} {dt.year}, {dt.hour:02d}:{dt.minute:02d}"


def _format_indonesian_price(price):
    """Format price as 'Rp 6.000' with Indonesian thousand separator."""
    try:
        amount = float(price or 0)
    except (TypeError, ValueError):
        amount = 0
    return "Rp {:,.0f}".format(amount).replace(",", ".")


def _extract_party(payload, key):
    """Pull a {nama, telepon, alamat} block from request payload, sanitized."""
    block = payload.get(key) or {}
    if not isinstance(block, dict):
        return {}
    party = {}
    for field in ('nama', 'telepon', 'alamat'):
        value = block.get(field)
        if value is not None:
            party[field] = str(value).strip()
    return party


def _package_metadata_from_request():
    """Build sender/recipient/service + mitra identity from request + session.

    Returns a dict to merge into package_data. Empty/absent body yields only
    the mitra identity (preserving legacy behavior for callers with no body).
    """
    payload = request.get_json(silent=True) or {}
    meta = {}

    sender = _extract_party(payload, 'sender')
    recipient = _extract_party(payload, 'recipient')
    if sender:
        meta['sender'] = sender
    if recipient:
        meta['recipient'] = recipient

    user = current_user()
    if user:
        meta['mitra_id'] = user.get('mitra_id')
        meta['mitra_name'] = user.get('name')

    return meta, payload


@main_bp.route('/receipt/<package_id>')
@role_required(ROLE_MITRA)
def receipt(package_id):
    """Render printable receipt for a package."""
    package = _get_scoped_package(package_id)

    if not package:
        return render_template(
            'dashboard.html',
            status=system_status,
            history=[],
            error="Paket tidak ditemukan"
        ), 404

    package_display_id = "PKT-" + str(package.get('id', '')).zfill(5)
    formatted_timestamp = _format_indonesian_datetime(package.get('timestamp'))
    formatted_price = _format_indonesian_price(package.get('price', 0))
    printed_at = _format_indonesian_datetime(datetime.now().isoformat())

    return render_template(
        'receipt.html',
        package=package,
        package_display_id=package_display_id,
        formatted_timestamp=formatted_timestamp,
        formatted_price=formatted_price,
        printed_at=printed_at,
    )


@main_bp.route('/receipt/<package_id>.pdf')
@role_required(ROLE_MITRA)
def receipt_pdf(package_id):
    """Download receipt as a PDF file."""
    package = _get_scoped_package(package_id)

    if not package:
        return jsonify({
            'success': False,
            'error': 'Paket tidak ditemukan'
        }), 404

    from web.pdf_receipt import build_receipt_pdf
    pdf_bytes = build_receipt_pdf(package)

    filename = "resi-PKT-" + str(package.get('id', '')).zfill(5) + ".pdf"
    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': 'attachment; filename="' + filename + '"'
        }
    )


@main_bp.route('/api/evidence/<package_id>')
@role_required(ROLE_MITRA)
def package_evidence(package_id):
    """Serve the detection evidence image for a package (read-only).

    Keyed by package_id (path comes from DB, never the client) + per-mitra
    scope + path confined to PROGRAM_PYTHON_BASE -> path traversal not possible.
    """
    import os
    from flask import send_file
    from config.settings import PROGRAM_PYTHON_BASE

    package = _get_scoped_package(package_id)
    if not package:
        return jsonify({'success': False, 'error': 'Paket tidak ditemukan'}), 404

    rel = (package.get('detection_image') or '').strip()
    if not rel or not PROGRAM_PYTHON_BASE:
        return jsonify({'success': False,
                        'error': 'Bukti gambar tidak tersedia untuk paket ini.'}), 404

    base = os.path.realpath(PROGRAM_PYTHON_BASE)
    target = os.path.realpath(os.path.join(base, rel))
    if not (target == base or target.startswith(base + os.sep)) or not os.path.isfile(target):
        return jsonify({'success': False,
                        'error': 'Bukti gambar tidak ditemukan.'}), 404

    return send_file(target, mimetype='image/jpeg')


@main_bp.route('/manual')
@role_required(ROLE_MITRA)
def manual():
    """Manual measurement page"""
    return render_template('manual.html',
                          status=system_status)


# =============================================================================
# API Endpoints
# =============================================================================
# API Endpoints
# =============================================================================

@api_bp.route('/status', methods=['GET'])
@api_login_required
def get_status():
    """Get current system status"""
    storage = get_storage()
    stats = storage.get_statistics()
    
    return jsonify({
        'success': True,
        'data': {
            'mode': system_status['mode'],
            'mode_info': system_status['mode_info'],
            'is_running': system_status['is_running'],
            'last_package': system_status['last_package'],
            'statistics': stats.get('by_service_type', system_status['total_today']),
            'storage_backend': _storage_backend,
            'timestamp': datetime.now().isoformat()
        }
    })


@api_bp.route('/measure', methods=['POST'])
@api_login_required
def trigger_measurement():
    """Trigger a measurement cycle"""
    global system_status
    
    # Check if already running
    if system_status['is_running']:
        return jsonify({
            'success': False,
            'error': 'System is already running a measurement cycle'
        }), 409
    
    # Set running flag
    system_status['is_running'] = True
    
    try:
        from config.settings import (
            is_mock_mode, HARDWARE_MODE, MEASUREMENT_MODE,
            MEASUREMENT_SOURCE_PATH, PROGRAM_PYTHON_BASE,
            MEASUREMENT_MAX_AGE_SECONDS
        )

        storage = get_storage()
        use_file = should_use_file_bridge(HARDWARE_MODE, MEASUREMENT_MODE)
        package_meta, _payload = _package_metadata_from_request()

        if MEASUREMENT_MODE == 'in_process':
            from web.measurement_engine import (
                measure_real,
                MeasurementUnavailableError,
                NeedCalibrationError,
                MeasurementTimeoutError,
                MeasurementEngineError,
            )

            try:
                mapped = measure_real()
            except NeedCalibrationError as e:
                log.warning("Measurement needs calibration", error=str(e))
                return jsonify({
                    'success': False,
                    'error': 'Sistem belum dikalibrasi. ' + str(e),
                    'error_type': 'need_calibration'
                }), 422
            except MeasurementTimeoutError as e:
                log.warning("Measurement timeout", error=str(e))
                return jsonify({
                    'success': False,
                    'error': 'Paket tidak terdeteksi. Pastikan paket berada '
                             'di area ukur, lalu coba lagi.',
                    'error_type': 'timeout'
                }), 422
            except MeasurementUnavailableError as e:
                log.error("Measurement hardware unavailable", error=str(e))
                return jsonify({
                    'success': False,
                    'error': 'Perangkat pengukuran tidak tersedia di sistem ini.',
                    'error_type': 'unavailable'
                }), 503
            except MeasurementEngineError as e:
                log.error("Measurement engine error", error=str(e))
                return jsonify({
                    'success': False,
                    'error': str(e),
                    'error_type': 'measurement_engine'
                }), 422

            service_type, price = classify_package(mapped['chargeable_weight'])

            package_data = {
                'dimensions': {
                    'panjang': mapped['panjang'],
                    'lebar': mapped['lebar'],
                    'tinggi': mapped['tinggi']
                },
                'weight': {
                    'aktual': mapped['berat_aktual'],
                    'volumetrik': mapped['berat_volumetrik'],
                    'chargeable': mapped['chargeable_weight'],
                    'source': mapped['chargeable_source']
                },
                'measurement_id': mapped['measurement_id'],
                'service_type': service_type,
                'price': price,
                'detection_image': mapped['detection_image'],
                'data_source': 'in_process',
                **package_meta
            }

            package_id = storage.save_package(package_data)

            log.operation("Package measured (in-process)",
                package_id=package_id,
                measurement_id=mapped['measurement_id'],
                service_type=service_type,
                weight=mapped['chargeable_weight'],
                price=price,
                backend=_storage_backend)

            package = {
                'id': package_id,
                'timestamp': mapped['timestamp'],
                **package_data
            }

            system_status['last_package'] = package
            system_status['total_today'][service_type] += 1

            broadcast_event('package_added', {
                'package': package,
                'statistics': {
                    'total_today': sum(system_status['total_today'].values()),
                    'by_type': dict(system_status['total_today'])
                }
            })

            return jsonify({
                'success': True,
                'data': package
            })

        if use_file:
            result = get_measurement_from_file(
                MEASUREMENT_SOURCE_PATH,
                PROGRAM_PYTHON_BASE,
                MEASUREMENT_MAX_AGE_SECONDS
            )

            service_type, price = classify_package(result.chargeable_weight)

            package_data = {
                'dimensions': {
                    'panjang': result.panjang,
                    'lebar': result.lebar,
                    'tinggi': result.tinggi
                },
                'weight': {
                    'aktual': result.berat_aktual,
                    'volumetrik': result.berat_volumetrik,
                    'chargeable': result.chargeable_weight,
                    'source': result.chargeable_source
                },
                'measurement_id': result.measurement_id,
                'service_type': service_type,
                'price': price,
                'detection_image': result.detection_image,
                'data_source': 'file_bridge',
                **package_meta
            }

            package_id = storage.save_package(package_data)

            log.operation("Package measured (file bridge)",
                package_id=package_id,
                measurement_id=result.measurement_id,
                service_type=service_type,
                weight=result.chargeable_weight,
                price=price,
                backend=_storage_backend)

            package = {
                'id': package_id,
                'timestamp': result.timestamp,
                **package_data
            }

            system_status['last_package'] = package
            system_status['total_today'][service_type] += 1

            broadcast_event('package_added', {
                'package': package,
                'statistics': {
                    'total_today': sum(system_status['total_today'].values()),
                    'by_type': dict(system_status['total_today'])
                }
            })

            return jsonify({
                'success': True,
                'data': package
            })

        elif is_mock_mode():
            import random

            panjang = round(random.uniform(5, 23), 1)
            lebar = round(random.uniform(5, 23), 1)
            tinggi = round(random.uniform(5, 23), 1)
            berat_aktual = round(random.uniform(50, 2000), 1)
            berat_volumetrik = round((panjang * lebar * tinggi) / 6000 * 1000, 1)
            chargeable = max(berat_aktual, berat_volumetrik)

            service_type, price = classify_package(chargeable)

            package_data = {
                'dimensions': {
                    'panjang': panjang,
                    'lebar': lebar,
                    'tinggi': tinggi
                },
                'weight': {
                    'aktual': berat_aktual,
                    'volumetrik': berat_volumetrik,
                    'chargeable': chargeable
                },
                'service_type': service_type,
                'price': price,
                'data_source': 'mock',
                **package_meta
            }

            package_id = storage.save_package(package_data)

            log.operation("Package measured (mock)",
                package_id=package_id,
                service_type=service_type,
                weight=chargeable,
                price=price,
                backend=_storage_backend)

            package = {
                'id': package_id,
                'timestamp': datetime.now().isoformat(),
                **package_data
            }

            system_status['last_package'] = package
            system_status['total_today'][service_type] += 1

            broadcast_event('package_added', {
                'package': package,
                'statistics': {
                    'total_today': sum(system_status['total_today'].values()),
                    'by_type': dict(system_status['total_today'])
                }
            })

            return jsonify({
                'success': True,
                'data': package
            })

        else:
            return jsonify({
                'success': False,
                'error': 'Mode pengukuran tidak dikenali. '
                         'Set MEASUREMENT_MODE=file atau MEASUREMENT_MODE=mock.'
            }), 501
            
    except MeasurementBridgeError as e:
        log.warning("Measurement bridge error", error=str(e))
        return jsonify({
            'success': False,
            'error': str(e),
            'error_type': 'measurement_bridge'
        }), 422
    except Exception as e:
        log.error("Measurement failed", exception=e)
        return jsonify({
            'success': False,
            'error': 'Terjadi kesalahan sistem. Silakan coba lagi.'
        }), 500
    finally:
        system_status['is_running'] = False


@api_bp.route('/manual', methods=['POST'])
@api_login_required
def manual_entry():
    """Save a package from manual operator input (alat error / fallback)."""
    payload = request.get_json(silent=True) or {}

    try:
        panjang = float(payload.get('panjang') or 0)
        lebar = float(payload.get('lebar') or 0)
        tinggi = float(payload.get('tinggi') or 0)
        berat_aktual = float(payload.get('berat_aktual') or 0)
    except (TypeError, ValueError):
        return jsonify({
            'success': False,
            'error': 'Dimensi dan berat harus berupa angka.'
        }), 422

    if panjang <= 0 or lebar <= 0 or tinggi <= 0 or berat_aktual <= 0:
        return jsonify({
            'success': False,
            'error': 'Dimensi dan berat harus lebih dari 0.'
        }), 422

    alasan = (payload.get('alasan') or '').strip()
    if not alasan:
        return jsonify({
            'success': False,
            'error': 'Alasan input manual wajib diisi untuk audit.'
        }), 422

    berat_volumetrik = round((panjang * lebar * tinggi) / 6000 * 1000, 1)
    chargeable = max(berat_aktual, berat_volumetrik)
    service_type, price = classify_package(chargeable)

    package_meta, _payload = _package_metadata_from_request()

    storage = get_storage()
    package_data = {
        'dimensions': {
            'panjang': round(panjang, 2),
            'lebar': round(lebar, 2),
            'tinggi': round(tinggi, 2)
        },
        'weight': {
            'aktual': round(berat_aktual, 1),
            'volumetrik': berat_volumetrik,
            'chargeable': chargeable
        },
        'service_type': service_type,
        'price': price,
        'alasan_manual': alasan,
        'data_source': 'manual',
        **package_meta
    }

    package_id = storage.save_package(package_data)

    log.operation("Package measured (manual)",
        package_id=package_id,
        service_type=service_type,
        weight=chargeable,
        price=price,
        reason=alasan,
        backend=_storage_backend)

    package = {
        'id': package_id,
        'timestamp': datetime.now().isoformat(),
        **package_data
    }

    system_status['last_package'] = package
    system_status['total_today'][service_type] += 1

    broadcast_event('package_added', {
        'package': package,
        'statistics': {
            'total_today': sum(system_status['total_today'].values()),
            'by_type': dict(system_status['total_today'])
        }
    })

    return jsonify({
        'success': True,
        'data': package
    })


@api_bp.route('/history', methods=['GET'])
@api_login_required
def get_history():
    """Get package history from storage"""
    storage = get_storage()
    
    # Query parameters
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    service_type = request.args.get('type', None)
    
    # Get packages from storage
    all_packages = _scope_packages(storage.get_all_packages(limit + offset + 100))
    
    # Filter by type if specified
    if service_type:
        filtered = [p for p in all_packages if p.get('service_type') == service_type]
    else:
        filtered = all_packages
    
    # Apply pagination
    paginated = filtered[offset:offset + limit]
    
    return jsonify({
        'success': True,
        'data': {
            'packages': paginated,
            'total': len(filtered),
            'limit': limit,
            'offset': offset,
            'source': _storage_backend
        }
    })


@api_bp.route('/history/<package_id>', methods=['GET'])
@api_login_required
def get_package(package_id):
    """Get single package by ID"""
    package = _get_scoped_package(package_id)
    
    if package:
        return jsonify({
            'success': True,
            'data': package
        })
    
    return jsonify({
        'success': False,
        'error': f'Package {package_id} not found'
    }), 404


@api_bp.route('/statistics', methods=['GET'])
@api_login_required
def get_statistics():
    """Get sorting statistics from storage"""
    storage = get_storage()
    stats = storage.get_statistics()
    
    return jsonify({
        'success': True,
        'data': {
            'total_packages': stats.get('total_packages', 0),
            'total_revenue': stats.get('total_revenue', 0),
            'by_service_type': stats.get('by_service_type', {}),
            'source': _storage_backend,
            'timestamp': datetime.now().isoformat()
        }
    })


@api_bp.route('/reset', methods=['POST'])
@api_role_required(ROLE_ADMIN)
def reset_statistics():
    """Reset daily statistics (admin only: menghapus data semua mitra)"""
    global system_status
    
    storage = get_storage()
    
    # Reset storage if it has reset_data method
    if hasattr(storage, 'reset_data'):
        storage.reset_data()
    
    # Reset runtime status
    system_status['total_today'] = {
        'REGULER': 0,
        'EXPRESS': 0,
        'KARGO': 0
    }
    system_status['last_package'] = None
    
    return jsonify({
        'success': True,
        'message': 'Statistics reset successfully',
        'storage_reset': True
    })


@api_bp.route('/sync', methods=['POST'])
@api_login_required
def force_sync():
    """Sinkronisasi cloud tidak berlaku (penyimpanan lokal SQLite offline-first)."""
    return jsonify({
        'success': False,
        'message': 'Penyimpanan lokal (SQLite). Sinkronisasi cloud tidak diperlukan.'
    }), 400


@api_bp.route('/hardware/status', methods=['GET'])
@api_login_required
def hardware_status():
    """Status koneksi hardware (kamera+GPIO dipegang web atau tidak)."""
    from config.settings import MEASUREMENT_MODE
    try:
        from web.measurement_engine import is_session_active
        connected = is_session_active()
    except Exception:
        connected = False
    return jsonify({
        'success': True,
        'data': {'connected': connected, 'mode': MEASUREMENT_MODE}
    })


@api_bp.route('/hardware/connect', methods=['POST'])
@role_required(ROLE_MITRA)
def hardware_connect():
    """Klaim kamera+GPIO untuk web (sesi pengukuran in_process)."""
    from web.measurement_engine import (
        connect_session, MeasurementUnavailableError,
        NeedCalibrationError, MeasurementEngineError,
    )
    try:
        result = connect_session()
    except NeedCalibrationError as e:
        return jsonify({'success': False, 'error': 'Belum dikalibrasi. ' + str(e),
                        'error_type': 'need_calibration'}), 422
    except MeasurementUnavailableError as e:
        return jsonify({'success': False, 'error': str(e),
                        'error_type': 'unavailable'}), 503
    except MeasurementEngineError as e:
        return jsonify({'success': False, 'error': str(e)}), 422
    except Exception as e:
        return jsonify({'success': False,
                        'error': 'Gagal connect hardware: ' + str(e)}), 500
    return jsonify({'success': True, 'data': result,
                    'message': 'Hardware terhubung. Kamera & sensor siap.'})


@api_bp.route('/hardware/disconnect', methods=['POST'])
@role_required(ROLE_MITRA)
def hardware_disconnect():
    """Lepas kamera+GPIO supaya program lain (tahap14 standalone) bisa pakai."""
    from web.measurement_engine import disconnect_session
    try:
        result = disconnect_session()
    except Exception as e:
        return jsonify({'success': False,
                        'error': 'Gagal disconnect: ' + str(e)}), 500
    return jsonify({'success': True, 'data': result,
                    'message': 'Hardware dilepas. Program lain boleh memakai kamera/sensor.'})


@api_bp.route('/hardware/weight', methods=['GET'])
@api_login_required
def hardware_weight():
    """Baca berat loadcell saat ini (gram) untuk polling autopilot.

    connected=False jika sesi belum aktif (hardware belum di-Connect).
    """
    try:
        from web.measurement_engine import get_current_weight
        weight = get_current_weight()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    if weight is None:
        return jsonify({'success': True,
                        'data': {'connected': False, 'weight_g': None}})
    return jsonify({'success': True,
                    'data': {'connected': True, 'weight_g': round(weight, 1)}})

# =============================================================================
# Server-Sent Events (SSE) for Real-time Updates
# =============================================================================

def broadcast_event(event_type: str, data: dict):
    """
    Broadcast event to all connected SSE clients
    
    Args:
        event_type: Event name (e.g., 'package_added', 'stats_updated')
        data: Event data to send
    """
    with _event_lock:
        dead_queues = []
        for q in _event_queues:
            try:
                q.put_nowait({
                    'event': event_type,
                    'data': data,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception:
                dead_queues.append(q)
        
        # Remove disconnected clients
        for q in dead_queues:
            _event_queues.remove(q)


@api_bp.route('/events', methods=['GET'])
@api_login_required
def stream_events():
    """
    SSE endpoint for real-time dashboard updates
    
    Client connects and receives events as they happen:
    - package_added: New package measured
    - stats_updated: Statistics changed
    - system_status: System status changed
    
    Usage:
        const evtSource = new EventSource('/api/events');
        evtSource.onmessage = (e) => { console.log(e.data); };
    """
    def event_stream():
        # Create queue for this client
        q = queue.Queue(maxsize=100)
        
        with _event_lock:
            _event_queues.append(q)
        
        try:
            # Send initial connection event
            yield f"data: {json.dumps({'event': 'connected', 'timestamp': datetime.now().isoformat()})}\n\n"
            
            # Keep connection alive and send events
            while True:
                try:
                    # Wait for event with timeout (for keepalive)
                    event = q.get(timeout=30)
                    yield f"data: {json.dumps(event)}\n\n"
                except queue.Empty:
                    # Send keepalive ping
                    yield ": keepalive\n\n"
                    
        finally:
            with _event_lock:
                if q in _event_queues:
                    _event_queues.remove(q)
    
    return Response(
        event_stream(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


@api_bp.route('/events/test', methods=['POST'])
@api_login_required
def test_event():
    """Test SSE by broadcasting a test event"""
    broadcast_event('test', {
        'message': 'SSE test event',
        'connected_clients': len(_event_queues)
    })
    
    return jsonify({
        'success': True,
        'connected_clients': len(_event_queues)
    })
