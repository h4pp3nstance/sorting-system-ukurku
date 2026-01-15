"""
Dimension Detector
Main module for detecting package dimensions from camera images
"""

from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    np = None

from .preprocessor import ImagePreprocessor, create_preprocessor, PreprocessConfig
from .calibrator import Calibrator, create_calibrator


@dataclass
class DimensionResult:
    """Result of dimension detection"""
    # Detected dimensions in centimeters
    length_cm: float = 0.0
    width_cm: float = 0.0
    height_cm: float = 0.0
    
    # Detection confidence (0-1)
    confidence: float = 0.0
    
    # Raw pixel measurements
    length_pixels: int = 0
    width_pixels: int = 0
    height_pixels: int = 0
    
    # Contour area for validation
    contour_area: int = 0
    
    # Detection status
    success: bool = False
    error_message: str = ""
    
    @property
    def volume_cm3(self) -> float:
        """Calculate volume in cubic centimeters"""
        return self.length_cm * self.width_cm * self.height_cm
    
    @property
    def volumetric_weight_grams(self) -> float:
        """Calculate volumetric weight in grams"""
        # Formula: (L × W × H) / 6000 × 1000
        return (self.volume_cm3 / 6000) * 1000
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'length_cm': round(self.length_cm, 1),
            'width_cm': round(self.width_cm, 1),
            'height_cm': round(self.height_cm, 1),
            'volume_cm3': round(self.volume_cm3, 1),
            'volumetric_weight_g': round(self.volumetric_weight_grams, 1),
            'confidence': round(self.confidence, 2),
            'success': self.success,
        }


class DimensionDetector:
    """
    Detects package dimensions from camera images
    
    Uses two cameras:
    - Top camera: Measures length and width
    - Side camera: Measures height
    
    Algorithm:
    1. Preprocess image (grayscale, blur, edge detection)
    2. Find contours
    3. Filter contours by area and shape
    4. Calculate bounding rectangle
    5. Convert pixels to centimeters using calibration
    """
    
    # Minimum contour area to consider (filters noise)
    MIN_CONTOUR_AREA = 1000
    
    # Aspect ratio bounds for rectangular packages
    MIN_ASPECT_RATIO = 0.1
    MAX_ASPECT_RATIO = 10.0
    
    def __init__(
        self,
        calibrator_top: Optional[Calibrator] = None,
        calibrator_side: Optional[Calibrator] = None,
        preprocessor: Optional[ImagePreprocessor] = None,
        use_mock: bool = False
    ):
        """
        Initialize dimension detector
        
        Args:
            calibrator_top: Calibrator for top camera
            calibrator_side: Calibrator for side camera
            preprocessor: Image preprocessor
            use_mock: Use mock implementations
        """
        self._use_mock = use_mock or not CV2_AVAILABLE
        
        # Create components
        self.calibrator_top = calibrator_top or create_calibrator("top", use_mock)
        self.calibrator_side = calibrator_side or create_calibrator("side", use_mock)
        self.preprocessor = preprocessor or create_preprocessor(use_mock)
        
        print(f"[DimensionDetector] Initialized (mock={self._use_mock})")
    
    def detect_from_top(self, image: 'np.ndarray') -> DimensionResult:
        """
        Detect length and width from top camera image
        
        Args:
            image: BGR image from top camera
            
        Returns:
            DimensionResult with length_cm and width_cm
        """
        if self._use_mock:
            return self._mock_detect_top()
        
        result = DimensionResult()
        
        try:
            # Preprocess
            edges = self.preprocessor.preprocess(image)
            
            # Find contours
            contours, _ = cv2.findContours(
                edges,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE
            )
            
            if not contours:
                result.error_message = "No contours found"
                return result
            
            # Find the largest contour (package)
            package_contour = self._find_package_contour(contours)
            
            if package_contour is None:
                result.error_message = "No valid package contour found"
                return result
            
            # Get minimum area rectangle (handles rotated packages)
            rect = cv2.minAreaRect(package_contour)
            box = cv2.boxPoints(rect)
            
            # Get dimensions in pixels
            width_px = rect[1][0]
            height_px = rect[1][1]
            
            # Ensure length >= width
            if width_px > height_px:
                result.length_pixels = int(width_px)
                result.width_pixels = int(height_px)
            else:
                result.length_pixels = int(height_px)
                result.width_pixels = int(width_px)
            
            # Convert to centimeters
            result.length_cm = self.calibrator_top.pixels_to_cm(result.length_pixels)
            result.width_cm = self.calibrator_top.pixels_to_cm(result.width_pixels)
            
            # Calculate confidence based on contour quality
            result.contour_area = int(cv2.contourArea(package_contour))
            result.confidence = self._calculate_confidence(package_contour, rect)
            
            result.success = True
            
        except Exception as e:
            result.error_message = str(e)
        
        return result
    
    def detect_from_side(self, image: 'np.ndarray') -> DimensionResult:
        """
        Detect height from side camera image
        
        Args:
            image: BGR image from side camera
            
        Returns:
            DimensionResult with height_cm
        """
        if self._use_mock:
            return self._mock_detect_side()
        
        result = DimensionResult()
        
        try:
            # Preprocess
            edges = self.preprocessor.preprocess(image)
            
            # Find contours
            contours, _ = cv2.findContours(
                edges,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE
            )
            
            if not contours:
                result.error_message = "No contours found"
                return result
            
            # Find package contour
            package_contour = self._find_package_contour(contours)
            
            if package_contour is None:
                result.error_message = "No valid package contour found"
                return result
            
            # Get bounding rectangle (upright)
            x, y, w, h = cv2.boundingRect(package_contour)
            
            # Height is the vertical dimension
            result.height_pixels = h
            result.height_cm = self.calibrator_side.pixels_to_cm(h)
            
            # Also get width from side view for validation
            result.width_pixels = w
            
            # Calculate confidence
            result.contour_area = int(cv2.contourArea(package_contour))
            result.confidence = min(1.0, result.contour_area / 50000)
            
            result.success = True
            
        except Exception as e:
            result.error_message = str(e)
        
        return result
    
    def detect_dimensions(
        self,
        image_top: 'np.ndarray',
        image_side: 'np.ndarray'
    ) -> DimensionResult:
        """
        Detect all dimensions from both cameras
        
        Args:
            image_top: Image from top camera
            image_side: Image from side camera
            
        Returns:
            Combined DimensionResult with all measurements
        """
        # Detect from top
        top_result = self.detect_from_top(image_top)
        
        # Detect from side
        side_result = self.detect_from_side(image_side)
        
        # Combine results
        combined = DimensionResult(
            length_cm=top_result.length_cm,
            width_cm=top_result.width_cm,
            height_cm=side_result.height_cm,
            length_pixels=top_result.length_pixels,
            width_pixels=top_result.width_pixels,
            height_pixels=side_result.height_pixels,
            contour_area=max(top_result.contour_area, side_result.contour_area),
            confidence=(top_result.confidence + side_result.confidence) / 2,
            success=top_result.success and side_result.success,
        )
        
        if not combined.success:
            errors = []
            if top_result.error_message:
                errors.append(f"Top: {top_result.error_message}")
            if side_result.error_message:
                errors.append(f"Side: {side_result.error_message}")
            combined.error_message = "; ".join(errors)
        
        return combined
    
    def _find_package_contour(
        self,
        contours: List['np.ndarray']
    ) -> Optional['np.ndarray']:
        """
        Find the contour most likely to be the package
        
        Filters by:
        - Minimum area
        - Aspect ratio
        - Convexity
        
        Args:
            contours: List of contours
            
        Returns:
            Best package contour or None
        """
        valid_contours = []
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Filter by area
            if area < self.MIN_CONTOUR_AREA:
                continue
            
            # Get bounding rect for aspect ratio
            x, y, w, h = cv2.boundingRect(contour)
            if h == 0:
                continue
            
            aspect_ratio = w / h
            
            # Filter by aspect ratio
            if not (self.MIN_ASPECT_RATIO < aspect_ratio < self.MAX_ASPECT_RATIO):
                continue
            
            valid_contours.append((contour, area))
        
        if not valid_contours:
            return None
        
        # Return largest valid contour
        valid_contours.sort(key=lambda x: x[1], reverse=True)
        return valid_contours[0][0]
    
    def _calculate_confidence(
        self,
        contour: 'np.ndarray',
        rect: Tuple
    ) -> float:
        """
        Calculate detection confidence
        
        Based on:
        - Contour area vs rect area (rectangularity)
        - Contour perimeter smoothness
        """
        contour_area = cv2.contourArea(contour)
        rect_area = rect[1][0] * rect[1][1]
        
        if rect_area == 0:
            return 0.0
        
        # Rectangularity (how close to rectangle)
        rectangularity = contour_area / rect_area
        
        # Normalize to 0-1 (0.5-1.0 is good for rectangles)
        confidence = min(1.0, rectangularity * 1.5)
        
        return confidence
    
    def _mock_detect_top(self) -> DimensionResult:
        """Mock detection for top camera"""
        import random
        
        length = round(random.uniform(10, 25), 1)
        width = round(random.uniform(8, 20), 1)
        
        # Ensure length >= width
        if width > length:
            length, width = width, length
        
        return DimensionResult(
            length_cm=length,
            width_cm=width,
            length_pixels=int(length * 50),
            width_pixels=int(width * 50),
            confidence=0.85,
            success=True
        )
    
    def _mock_detect_side(self) -> DimensionResult:
        """Mock detection for side camera"""
        import random
        
        height = round(random.uniform(5, 20), 1)
        
        return DimensionResult(
            height_cm=height,
            height_pixels=int(height * 50),
            confidence=0.80,
            success=True
        )
    
    def visualize_detection(
        self,
        image: 'np.ndarray',
        contour: 'np.ndarray',
        result: DimensionResult
    ) -> 'np.ndarray':
        """
        Draw detection visualization on image
        
        Args:
            image: Original BGR image
            contour: Detected contour
            result: Detection result
            
        Returns:
            Image with visualization overlay
        """
        if not CV2_AVAILABLE:
            return image
        
        output = image.copy()
        
        # Draw contour
        cv2.drawContours(output, [contour], -1, (0, 255, 0), 2)
        
        # Draw bounding rectangle
        rect = cv2.minAreaRect(contour)
        box = cv2.boxPoints(rect)
        box = np.int32(box)
        cv2.drawContours(output, [box], -1, (0, 0, 255), 2)
        
        # Add dimension text
        text = f"L:{result.length_cm:.1f} W:{result.width_cm:.1f} H:{result.height_cm:.1f} cm"
        cv2.putText(
            output, text,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7, (255, 255, 255), 2
        )
        
        return output


def create_dimension_detector(use_mock: bool = False) -> DimensionDetector:
    """
    Factory function for dimension detector
    
    Args:
        use_mock: If True, use mock implementations
        
    Returns:
        DimensionDetector instance
    """
    return DimensionDetector(use_mock=use_mock or not CV2_AVAILABLE)
