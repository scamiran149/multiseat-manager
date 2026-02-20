import sys
import pprint
from src.core.scanner import HardwareScanner
from src.core.loginctl_api import get_current_assignments

scanner = HardwareScanner()
hardware_data = scanner.full_scan()

assignments = get_current_assignments()

live_mapping_list = []
for syspath, seat in assignments.items():
    if seat == "seat1":
        live_mapping_list.append(syspath)

print("--- SEAT1 LIVE ASSIGNMENTS ---")
for x in live_mapping_list:
    if "input" in x:
        print(x)

print("\n--- HW DATA INPUTS ---")
for inp in hardware_data.get("inputs", []):
    if "Logitech" in inp.get('name', '') or "Telink" in inp.get('name', ''):
        print(f"Name: {inp.get('name')}")
        print(f"  syspath: {inp.get('syspath')}")
        print(f"  persistent_id: {inp.get('persistent_id')}")

