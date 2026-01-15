"""
Mock Camera
Simulator yang menggunakan test images
"""

import os
import random
from typing import Optional, List
from hal.interfaces import ICamera

# Coba import cv2, fallback ke dummy jika tidak ada
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("[Warning] OpenCV not available, using dummy mode")


class MockCamera(ICamera):
    """
    Mock implementation of Camera
    Loads test images from a folder for testing
    """
    
    def __init__(
        self,
        camera_id: str = "top",
        test_images_folder: Optional[str] = None
    ):
        """
        Args:
            camera_id: Identifier ("top" or "side")
            test_images_folder: Path to folder containing test images
        """
        self.camera_id = camera_id
        self.test_images_folder = test_images_folder or f"assets/test_images/{camera_id}"
        self._initialized = False
        self._image_files: List[str] = []
        self._current_index = 0
    
    def setup(self) -> None:
        """Initialize mock camera"""
        print(f"[MockCamera-{self.camera_id}] Initializing mock camera...")
        
        # Check if test images folder exists
        if os.path.exists(self.test_images_folder):
            # Load list of test images
            valid_extensions = ('.jpg', '.jpeg', '.png', '.bmp')
            self._image_files = [
                os.path.join(self.test_images_folder, f)
                for f in os.listdir(self.test_images_folder)
                if f.lower().endswith(valid_extensions)
            ]
            print(f"[MockCamera-{self.camera_id}] Found {len(self._image_files)} test images")
        else:
            print(f"[MockCamera-{self.camera_id}] No test images folder, will generate dummy images")
        
        self._initialized = True
        print(f"[MockCamera-{self.camera_id}] Mock camera ready!")
    
    def capture(self) -> any:
        """
        Capture an image (from test folder or generate dummy)
        Returns:
            numpy array: Image frame (or None if no CV2)
        """
        if not self._initialized:
            raise RuntimeError("Camera not initialized. Call setup() first.")
        
        if not CV2_AVAILABLE:
            print(f"[MockCamera-{self.camera_id}] Captured dummy image (OpenCV not available)")
            return None
        
        if self._image_files:
            # Load image from test folder (cycle through)
            image_path = self._image_files[self._current_index]
            self._current_index = (self._current_index + 1) % len(self._image_files)
            
            img = cv2.imread(image_path)
            if img is not None:
                print(f"[MockCamera-{self.camera_id}] Loaded: {os.path.basename(image_path)}")
                return img
        
        # Generate dummy image if no test images
        return self._generate_dummy_image()
    
    def _generate_dummy_image(self) -> any:
        """Generate a dummy image with a rectangle (simulating package)"""
        if not CV2_AVAILABLE:
            return None
        
        # Create blank image
        height, width = 480, 640
        img = np.zeros((height, width, 3), dtype=np.uint8)
        img[:] = (200, 200, 200)  # Light gray background
        
        # Draw a rectangle (simulating package)
        pkg_width = random.randint(100, 300)
        pkg_height = random.randint(80, 250)
        x = (width - pkg_width) // 2
        y = (height - pkg_height) // 2
        
        cv2.rectangle(img, (x, y), (x + pkg_width, y + pkg_height), (139, 90, 43), -1)  # Brown box
        cv2.rectangle(img, (x, y), (x + pkg_width, y + pkg_height), (80, 50, 20), 2)  # Darker border
        
        print(f"[MockCamera-{self.camera_id}] Generated dummy image with box {pkg_width}x{pkg_height}")
        return img
    
    def release(self) -> None:
        """Release camera resources"""
        print(f"[MockCamera-{self.camera_id}] Camera released")
        self._initialized = False
    
    def set_test_image(self, image_path: str) -> None:
        """
        Set a specific image for deterministic testing
        Args:
            image_path: Path to specific test image
        """
        if os.path.exists(image_path):
            self._image_files = [image_path]
            self._current_index = 0
            print(f"[MockCamera-{self.camera_id}] Set fixed image: {image_path}")
        else:
            print(f"[MockCamera-{self.camera_id}] Warning: Image not found: {image_path}")


# Factory function
def create_camera(camera_id: str, mode: str = "mock") -> ICamera:
    """
    Factory untuk membuat camera
    Args:
        camera_id: "top" atau "side"
        mode: "mock" atau "real"
    Returns:
        ICamera implementation
    """
    if mode == "mock":
        return MockCamera(camera_id=camera_id)
    else:
        # TODO: Import dan return RealCamera
        raise NotImplementedError("Real Camera not implemented yet")
