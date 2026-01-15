"""
Camera Calibrator
Converts pixel measurements to real-world centimeters
"""

from typing import Optional, Tuple, Dict
from dataclasses import dataclass
import json
import os

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


@dataclass
class CalibrationData:
    """Calibration parameters"""
    # Pixels per centimeter (for each camera)
    pixels_per_cm_top: float = 50.0      # Top camera
    pixels_per_cm_side: float = 50.0     # Side camera
    
    # Camera distance from belt (cm)
    camera_height_top: float = 30.0
    camera_height_side: float = 25.0
    
    # Working area dimensions in pixels
    roi_top: Tuple[int, int, int, int] = (100, 100, 500, 500)  # x, y, w, h
    roi_side: Tuple[int, int, int, int] = (100, 100, 500, 200)
    
    # Reference object size for calibration
    reference_size_cm: float = 10.0  # Default 10cm reference


class Calibrator:
    """
    Handles camera calibration for accurate dimension measurement
    
    Supports:
    - ArUco marker calibration
    - Known-size reference object calibration
    - Manual pixel-per-cm configuration
    """
    
    # ArUco dictionary for markers
    ARUCO_DICT = cv2.aruco.DICT_4X4_50 if CV2_AVAILABLE else None
    
    def __init__(
        self,
        camera_id: str = "top",
        calibration_file: Optional[str] = None
    ):
        """
        Initialize calibrator
        
        Args:
            camera_id: 'top' or 'side'
            calibration_file: Path to saved calibration JSON
        """
        self.camera_id = camera_id
        self.calibration_file = calibration_file or f"config/calibration_{camera_id}.json"
        
        # Default calibration
        self.data = CalibrationData()
        
        # Try to load saved calibration
        self._load_calibration()
        
        # ArUco detector (if OpenCV available)
        if CV2_AVAILABLE:
            self._aruco_dict = cv2.aruco.getPredefinedDictionary(self.ARUCO_DICT)
            self._aruco_params = cv2.aruco.DetectorParameters()
            self._aruco_detector = cv2.aruco.ArucoDetector(
                self._aruco_dict,
                self._aruco_params
            )
    
    @property
    def pixels_per_cm(self) -> float:
        """Get pixels per cm for current camera"""
        if self.camera_id == "top":
            return self.data.pixels_per_cm_top
        return self.data.pixels_per_cm_side
    
    def pixels_to_cm(self, pixels: float) -> float:
        """
        Convert pixel measurement to centimeters
        
        Args:
            pixels: Measurement in pixels
            
        Returns:
            Measurement in centimeters
        """
        return pixels / self.pixels_per_cm
    
    def cm_to_pixels(self, cm: float) -> float:
        """
        Convert centimeter measurement to pixels
        
        Args:
            cm: Measurement in centimeters
            
        Returns:
            Measurement in pixels
        """
        return cm * self.pixels_per_cm
    
    def calibrate_from_reference(
        self,
        image: 'np.ndarray',
        reference_size_cm: float = 10.0
    ) -> bool:
        """
        Calibrate using a known-size reference object in the image
        
        Args:
            image: Image containing reference object
            reference_size_cm: Real size of reference object in cm
            
        Returns:
            True if calibration successful
        """
        if not CV2_AVAILABLE:
            return False
        
        # Try ArUco marker first
        corners, ids, _ = self._aruco_detector.detectMarkers(image)
        
        if ids is not None and len(ids) > 0:
            # Use first detected marker
            marker_corners = corners[0][0]
            
            # Calculate marker size in pixels
            side1 = np.linalg.norm(marker_corners[0] - marker_corners[1])
            side2 = np.linalg.norm(marker_corners[1] - marker_corners[2])
            marker_size_pixels = (side1 + side2) / 2
            
            # Calculate pixels per cm
            ppc = marker_size_pixels / reference_size_cm
            
            # Update calibration
            if self.camera_id == "top":
                self.data.pixels_per_cm_top = ppc
            else:
                self.data.pixels_per_cm_side = ppc
            
            self._save_calibration()
            return True
        
        return False
    
    def calibrate_from_contour(
        self,
        contour: 'np.ndarray',
        known_width_cm: float
    ) -> bool:
        """
        Calibrate using a detected contour with known width
        
        Args:
            contour: OpenCV contour
            known_width_cm: Real width in cm
            
        Returns:
            True if calibration successful
        """
        if not CV2_AVAILABLE:
            return False
        
        # Get bounding rectangle
        _, _, width_pixels, _ = cv2.boundingRect(contour)
        
        if width_pixels > 0:
            ppc = width_pixels / known_width_cm
            
            if self.camera_id == "top":
                self.data.pixels_per_cm_top = ppc
            else:
                self.data.pixels_per_cm_side = ppc
            
            self._save_calibration()
            return True
        
        return False
    
    def set_pixels_per_cm(self, value: float) -> None:
        """
        Manually set pixels per cm
        
        Args:
            value: Pixels per centimeter
        """
        if self.camera_id == "top":
            self.data.pixels_per_cm_top = value
        else:
            self.data.pixels_per_cm_side = value
        
        self._save_calibration()
    
    def get_roi(self) -> Tuple[int, int, int, int]:
        """Get Region of Interest for current camera"""
        if self.camera_id == "top":
            return self.data.roi_top
        return self.data.roi_side
    
    def set_roi(self, x: int, y: int, w: int, h: int) -> None:
        """Set Region of Interest"""
        roi = (x, y, w, h)
        if self.camera_id == "top":
            self.data.roi_top = roi
        else:
            self.data.roi_side = roi
        self._save_calibration()
    
    def crop_to_roi(self, image: 'np.ndarray') -> 'np.ndarray':
        """Crop image to ROI"""
        x, y, w, h = self.get_roi()
        return image[y:y+h, x:x+w]
    
    def _save_calibration(self) -> None:
        """Save calibration to JSON file"""
        try:
            os.makedirs(os.path.dirname(self.calibration_file), exist_ok=True)
            
            data = {
                'camera_id': self.camera_id,
                'pixels_per_cm_top': self.data.pixels_per_cm_top,
                'pixels_per_cm_side': self.data.pixels_per_cm_side,
                'camera_height_top': self.data.camera_height_top,
                'camera_height_side': self.data.camera_height_side,
                'roi_top': list(self.data.roi_top),
                'roi_side': list(self.data.roi_side),
                'reference_size_cm': self.data.reference_size_cm,
            }
            
            with open(self.calibration_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            print(f"[Calibrator] Warning: Could not save calibration: {e}")
    
    def _load_calibration(self) -> bool:
        """Load calibration from JSON file"""
        try:
            if os.path.exists(self.calibration_file):
                with open(self.calibration_file, 'r') as f:
                    data = json.load(f)
                
                self.data.pixels_per_cm_top = data.get('pixels_per_cm_top', 50.0)
                self.data.pixels_per_cm_side = data.get('pixels_per_cm_side', 50.0)
                self.data.camera_height_top = data.get('camera_height_top', 30.0)
                self.data.camera_height_side = data.get('camera_height_side', 25.0)
                self.data.roi_top = tuple(data.get('roi_top', [100, 100, 500, 500]))
                self.data.roi_side = tuple(data.get('roi_side', [100, 100, 500, 200]))
                self.data.reference_size_cm = data.get('reference_size_cm', 10.0)
                
                return True
        except Exception as e:
            print(f"[Calibrator] Warning: Could not load calibration: {e}")
        
        return False
    
    def to_dict(self) -> Dict:
        """Export calibration as dictionary"""
        return {
            'camera_id': self.camera_id,
            'pixels_per_cm': self.pixels_per_cm,
            'roi': self.get_roi(),
        }


class MockCalibrator:
    """Mock calibrator for testing without OpenCV"""
    
    def __init__(self, camera_id: str = "top", **kwargs):
        self.camera_id = camera_id
        self._pixels_per_cm = 50.0  # Default value
    
    @property
    def pixels_per_cm(self) -> float:
        return self._pixels_per_cm
    
    def pixels_to_cm(self, pixels: float) -> float:
        return pixels / self._pixels_per_cm
    
    def cm_to_pixels(self, cm: float) -> float:
        return cm * self._pixels_per_cm
    
    def set_pixels_per_cm(self, value: float) -> None:
        self._pixels_per_cm = value
    
    def calibrate_from_reference(self, image, reference_size_cm: float = 10.0) -> bool:
        return True  # Always succeeds in mock
    
    def crop_to_roi(self, image):
        return image
    
    def to_dict(self) -> Dict:
        return {
            'camera_id': self.camera_id,
            'pixels_per_cm': self._pixels_per_cm,
            'mock': True
        }


def create_calibrator(
    camera_id: str = "top",
    use_mock: bool = False,
    **kwargs
) -> Calibrator:
    """
    Factory function for calibrator
    
    Args:
        camera_id: 'top' or 'side'
        use_mock: If True, return mock calibrator
        
    Returns:
        Calibrator instance
    """
    if use_mock or not CV2_AVAILABLE:
        return MockCalibrator(camera_id, **kwargs)
    return Calibrator(camera_id, **kwargs)
