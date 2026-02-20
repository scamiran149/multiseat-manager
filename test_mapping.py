import sys
import pprint
from src.core.scanner import HardwareScanner
from src.core.loginctl_api import get_current_assignments

scanner = HardwareScanner()
hardware_data = scanner.full_scan()

assignments = get_current_assignments()
live_mapping = {}
for syspath, seat in assignments.items():
    if seat not in live_mapping:
        live_mapping[seat] = []
    live_mapping[seat].append(syspath)

print("--- LIVE MAPPING ---")
pprint.pprint(live_mapping)

print("--- HARDWARE DATA ---")
for gpu in hardware_data.get("graphics", []):
    print(f"GPU: {gpu.get('name')}")
    print(f"  syspath: {gpu.get('syspath')}")
    print(f"  pci_syspath: {gpu.get('pci_syspath')}")
    print(f"  persistent_id: {gpu.get('persistent_id')}")

for inp in hardware_data.get("inputs", []):
    print(f"Input: {inp.get('name')}")
    print(f"  syspath: {inp.get('syspath')}")
    print(f"  persistent_id: {inp.get('persistent_id')}")
