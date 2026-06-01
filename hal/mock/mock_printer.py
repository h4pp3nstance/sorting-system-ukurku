"""
Mock Thermal Printer
Output ke console atau file untuk testing
"""

import os
from datetime import datetime
from typing import Optional
from hal.interfaces import IPrinter, PackageData


class MockPrinter(IPrinter):
    """
    Mock implementation of Thermal Printer
    Outputs label to console and optionally to file
    """
    
    def __init__(self, output_folder: Optional[str] = None):
        """
        Args:
            output_folder: Folder untuk menyimpan output file (optional)
        """
        self.output_folder = output_folder or "output/labels"
        self._initialized = False
    
    def setup(self) -> None:
        """Initialize mock printer"""
        print("[MockPrinter] Initializing mock printer...")
        
        # Create output folder if needed
        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder, exist_ok=True)
            print(f"[MockPrinter] Created output folder: {self.output_folder}")
        
        self._initialized = True
        print("[MockPrinter] Mock printer ready!")
    
    def print_label(self, data: PackageData) -> bool:
        """
        Print label to console and file
        Args:
            data: Package data to print
        Returns:
            bool: True if successful
        """
        if not self._initialized:
            raise RuntimeError("Printer not initialized. Call setup() first.")
        
        # Generate label content
        label = self._generate_label(data)
        
        # Print to console
        print("\n" + "=" * 50)
        print("PRINTING LABEL")
        print("=" * 50)
        print(label)
        print("=" * 50 + "\n")
        
        # Save to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"label_{timestamp}.txt"
        filepath = os.path.join(self.output_folder, filename)
        
        try:
            with open(filepath, 'w') as f:
                f.write(label)
            print(f"[MockPrinter] Label saved to: {filepath}")
            return True
        except Exception as e:
            print(f"[MockPrinter] Error saving file: {e}")
            return False
    
    def _generate_label(self, data: PackageData) -> str:
        """Generate formatted label content"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Determine pricing (for display)
        price_map = {
            'REGULER': 6000,
            'EXPRESS': 12000,
            'KARGO': 5000
        }
        price = price_map.get(data.service_type, 0)
        
        label = f"""
╔══════════════════════════════════════════╗
║          SORTING SYSTEM LABEL            ║
╠══════════════════════════════════════════╣
║  Date: {timestamp}           ║
╠══════════════════════════════════════════╣
║  DIMENSI:                                ║
║    Panjang : {data.panjang:>10.1f} cm             ║
║    Lebar   : {data.lebar:>10.1f} cm             ║
║    Tinggi  : {data.tinggi:>10.1f} cm             ║
╠══════════════════════════════════════════╣
║  BERAT:                                  ║
║    Aktual      : {data.berat_aktual:>10.1f} gram         ║
║    Volumetrik  : {data.berat_volumetrik:>10.1f} gram         ║
║    Chargeable  : {data.chargeable_weight:>10.1f} gram         ║
╠══════════════════════════════════════════╣
║  LAYANAN:                                ║
║                                          ║
║     ╔═══════════════════════════╗        ║
║     ║   {data.service_type:^20}  ║        ║
║     ╚═══════════════════════════╝        ║
║                                          ║
║  BIAYA: Rp {price:,}                    ║
╚══════════════════════════════════════════╝
"""
        return label


# Factory function
def create_printer(mode: str = "mock") -> IPrinter:
    """Factory untuk printer"""
    if mode == "mock":
        return MockPrinter()
    else:
        raise NotImplementedError("Real printer not implemented yet")
