"""
Mode Helper - computes human-readable system mode label.
Single source of truth for operator-facing mode display.
"""
from config.settings import HARDWARE_MODE, MEASUREMENT_MODE, HardwareMode
from web.measurement_bridge import should_use_file_bridge


def get_system_mode_info() -> dict:
    """Return human-readable mode info for operator UI.

    Returns dict with keys:
        mode_id: str - internal identifier ('file', 'mock', 'unknown')
        label: str - short label for sidebar ('Mesin Ukur', 'Demo')
        description: str - longer description for status bar
        dot_class: str - CSS class for status dot color
    """
    if should_use_file_bridge(HARDWARE_MODE, MEASUREMENT_MODE):
        return {
            'mode_id': 'file',
            'label': 'Mesin Ukur',
            'description': 'Data dari alat ukur',
            'dot_class': 'status-dot--active'
        }
    elif HARDWARE_MODE == HardwareMode.MOCK.value:
        return {
            'mode_id': 'mock',
            'label': 'Demo',
            'description': 'Data simulasi untuk demo',
            'dot_class': 'status-dot--warning'
        }
    else:
        return {
            'mode_id': 'unknown',
            'label': 'Tidak Diketahui',
            'description': 'Konfigurasi tidak dikenali',
            'dot_class': 'status-dot--error'
        }
