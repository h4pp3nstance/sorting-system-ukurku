"""
Hardware Abstraction Layer - Interfaces
Abstract base classes untuk semua hardware components
"""

from abc import ABC, abstractmethod
from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class PackageData:
    """Data class untuk menyimpan informasi paket"""
    panjang: float  # cm
    lebar: float    # cm
    tinggi: float   # cm
    berat_aktual: float  # gram
    berat_volumetrik: float  # gram
    chargeable_weight: float  # gram
    service_type: str  # REGULER, EXPRESS, KARGO
    price: int  # Rupiah


class IWeightSensor(ABC):
    """Interface untuk sensor berat (Load Cell + HX711)"""
    
    @abstractmethod
    def setup(self) -> None:
        """Inisialisasi sensor"""
        pass
    
    @abstractmethod
    def read_weight(self) -> float:
        """
        Baca berat dalam gram
        Returns:
            float: Berat dalam gram (50-2000)
        """
        pass
    
    @abstractmethod
    def tare(self) -> None:
        """Reset timbangan ke nol"""
        pass


class ICamera(ABC):
    """Interface untuk kamera"""
    
    @abstractmethod
    def setup(self) -> None:
        """Inisialisasi kamera"""
        pass
    
    @abstractmethod
    def capture(self) -> any:
        """
        Capture image
        Returns:
            numpy array: Image frame
        """
        pass
    
    @abstractmethod
    def release(self) -> None:
        """Release kamera resource"""
        pass


class IInfraredSensor(ABC):
    """Interface untuk sensor infrared"""
    
    @abstractmethod
    def setup(self) -> None:
        """Inisialisasi sensor"""
        pass
    
    @abstractmethod
    def is_triggered(self) -> bool:
        """
        Cek apakah sensor terblokir objek
        Returns:
            bool: True jika ada objek
        """
        pass


class IMotor(ABC):
    """Interface untuk motor DC (conveyor)"""
    
    @abstractmethod
    def setup(self) -> None:
        """Inisialisasi motor"""
        pass
    
    @abstractmethod
    def start(self) -> None:
        """Jalankan motor"""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Hentikan motor"""
        pass


class IServo(ABC):
    """Interface untuk motor servo"""
    
    @abstractmethod
    def setup(self) -> None:
        """Inisialisasi servo"""
        pass
    
    @abstractmethod
    def set_angle(self, angle: int) -> None:
        """
        Set posisi servo
        Args:
            angle: Sudut servo (0-180)
        """
        pass
    
    @abstractmethod
    def reset(self) -> None:
        """Reset ke posisi default"""
        pass


class IPrinter(ABC):
    """Interface untuk thermal printer"""
    
    @abstractmethod
    def setup(self) -> None:
        """Inisialisasi printer"""
        pass
    
    @abstractmethod
    def print_label(self, data: PackageData) -> bool:
        """
        Cetak label paket
        Args:
            data: Data paket untuk dicetak
        Returns:
            bool: True jika berhasil
        """
        pass
