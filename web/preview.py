"""
Live Camera Preview - MJPEG via CameraService.

/video_feed melakukan streaming multipart/x-mixed-replace dari frame yang
disediakan CameraService (pemilik tunggal kamera). TIDAK membuka VideoCapture
sendiri: preview dan MeasurementSession berbagi satu sumber frame.
"""

import os
import time

from flask import Blueprint, Response, jsonify

from web.auth import role_required, ROLE_MITRA

preview_bp = Blueprint('preview', __name__)

_FPS = int(os.getenv("PREVIEW_FPS", "30"))
_QUALITY = int(os.getenv("PREVIEW_JPEG_QUALITY", "70"))


@preview_bp.route('/video_feed')
@role_required(ROLE_MITRA)
def video_feed():
    from web.measurement_engine import get_camera_service

    try:
        cam = get_camera_service()
        cam.start()
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Kamera tidak dapat dibuka untuk preview: ' + str(e)
        }), 503

    def generate():
        target_dt = 1.0 / _FPS if _FPS > 0 else 0
        cam.add_viewer()
        try:
            while True:
                t0 = time.time()
                if not cam.is_running():
                    break
                jpeg = cam.get_jpeg(quality=_QUALITY)
                if jpeg is not None:
                    yield (b"--frame\r\n"
                           b"Content-Type: image/jpeg\r\n"
                           b"Content-Length: " + str(len(jpeg)).encode() +
                           b"\r\n\r\n" + jpeg + b"\r\n")
                dt = time.time() - t0
                if target_dt and dt < target_dt:
                    time.sleep(target_dt - dt)
        finally:
            cam.remove_viewer()
            cam.release_if_idle()

    return Response(
        generate(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )
