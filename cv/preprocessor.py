"""
Image Preprocessor
Prepares images for dimension detection
"""

from typing import Optional, Tuple
from dataclasses import dataclass

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


@dataclass
class PreprocessConfig:
    """Configuration for image preprocessing"""
    # Gaussian blur kernel size (must be odd)
    blur_kernel: int = 5
    
    # Canny edge detection thresholds
    canny_low: int = 50
    canny_high: int = 150
    
    # Morphological operations
    morph_kernel_size: int = 3
    morph_iterations: int = 2
    
    # Contrast adjustment
    clahe_clip_limit: float = 2.0
    clahe_grid_size: Tuple[int, int] = (8, 8)


class ImagePreprocessor:
    """
    Preprocesses images for dimension detection
    
    Pipeline:
    1. Convert to grayscale
    2. Apply CLAHE for contrast enhancement
    3. Gaussian blur for noise reduction
    4. Canny edge detection
    5. Morphological operations (dilate/erode)
    """
    
    def __init__(self, config: Optional[PreprocessConfig] = None):
        """
        Initialize preprocessor
        
        Args:
            config: Preprocessing configuration
        """
        if not CV2_AVAILABLE:
            raise ImportError("OpenCV (cv2) is required for image preprocessing")
        
        self.config = config or PreprocessConfig()
        
        # Create CLAHE object
        self._clahe = cv2.createCLAHE(
            clipLimit=self.config.clahe_clip_limit,
            tileGridSize=self.config.clahe_grid_size
        )
        
        # Create morphological kernel
        self._morph_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (self.config.morph_kernel_size, self.config.morph_kernel_size)
        )
    
    def preprocess(self, image: 'np.ndarray') -> 'np.ndarray':
        """
        Apply full preprocessing pipeline
        
        Args:
            image: Input BGR image
            
        Returns:
            Binary edge image
        """
        # Step 1: Convert to grayscale
        gray = self.to_grayscale(image)
        
        # Step 2: Enhance contrast
        enhanced = self.enhance_contrast(gray)
        
        # Step 3: Blur
        blurred = self.apply_blur(enhanced)
        
        # Step 4: Edge detection
        edges = self.detect_edges(blurred)
        
        # Step 5: Morphological operations
        cleaned = self.apply_morphology(edges)
        
        return cleaned
    
    def to_grayscale(self, image: 'np.ndarray') -> 'np.ndarray':
        """Convert BGR image to grayscale"""
        if len(image.shape) == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return image
    
    def enhance_contrast(self, gray: 'np.ndarray') -> 'np.ndarray':
        """Apply CLAHE contrast enhancement"""
        return self._clahe.apply(gray)
    
    def apply_blur(self, image: 'np.ndarray') -> 'np.ndarray':
        """Apply Gaussian blur for noise reduction"""
        kernel_size = self.config.blur_kernel
        return cv2.GaussianBlur(image, (kernel_size, kernel_size), 0)
    
    def detect_edges(self, image: 'np.ndarray') -> 'np.ndarray':
        """Apply Canny edge detection"""
        return cv2.Canny(
            image,
            self.config.canny_low,
            self.config.canny_high
        )
    
    def apply_morphology(self, edges: 'np.ndarray') -> 'np.ndarray':
        """Apply morphological operations to clean up edges"""
        # Dilate to connect broken edges
        dilated = cv2.dilate(
            edges,
            self._morph_kernel,
            iterations=self.config.morph_iterations
        )
        
        # Erode to restore size
        eroded = cv2.erode(
            dilated,
            self._morph_kernel,
            iterations=self.config.morph_iterations - 1
        )
        
        return eroded
    
    def apply_threshold(
        self,
        gray: 'np.ndarray',
        method: str = 'otsu'
    ) -> 'np.ndarray':
        """
        Apply thresholding for binary image
        
        Args:
            gray: Grayscale image
            method: 'otsu', 'adaptive', or 'simple'
            
        Returns:
            Binary image
        """
        if method == 'otsu':
            _, binary = cv2.threshold(
                gray, 0, 255,
                cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
        elif method == 'adaptive':
            binary = cv2.adaptiveThreshold(
                gray, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                11, 2
            )
        else:  # simple
            _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        
        return binary


class MockImagePreprocessor:
    """
    Mock preprocessor for testing without OpenCV
    """
    
    def __init__(self, config: Optional[PreprocessConfig] = None):
        self.config = config or PreprocessConfig()
    
    def preprocess(self, image) -> None:
        """Return None (mock)"""
        return None
    
    def to_grayscale(self, image) -> None:
        return None
    
    def enhance_contrast(self, gray) -> None:
        return None
    
    def apply_blur(self, image) -> None:
        return None
    
    def detect_edges(self, image) -> None:
        return None
    
    def apply_morphology(self, edges) -> None:
        return None


def create_preprocessor(use_mock: bool = False) -> ImagePreprocessor:
    """
    Factory function for preprocessor
    
    Args:
        use_mock: If True, return mock preprocessor
        
    Returns:
        ImagePreprocessor instance
    """
    if use_mock or not CV2_AVAILABLE:
        return MockImagePreprocessor()
    return ImagePreprocessor()
