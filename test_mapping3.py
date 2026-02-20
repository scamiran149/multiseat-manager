import sys
import pprint
from src.core.scanner import HardwareScanner

scanner = HardwareScanner()
hardware_data = scanner.full_scan()

print("\n--- ALL HW DATA ---")
def print_keys(data, level=0):
    indent = "  " * level
    if isinstance(data, dict):
        for k, v in data.items():
            print(f"{indent}{k}:")
            print_keys(v, level + 1)
    elif isinstance(data, list):
        print(f"{indent}[List of {len(data)} items]")
        if len(data) > 0 and isinstance(data[0], dict):
            print_keys(data[0], level + 1)

print_keys(hardware_data)

def search_logitech(device_list, path=""):
    for item in device_list:
        if isinstance(item, dict):
            if "Logitech" in str(item.get("name", "")) or "Telink" in str(item.get("name", "")):
                print(f"FOUND: {item.get('name')} at {path} -> {item.get('syspath')}")
            for k, v in item.items():
                if isinstance(v, list):
                    search_logitech(v, path + f".{k}")

print("\n--- SEARCHING LOGITECH ---")
for k, v in hardware_data.items():
    if isinstance(v, list):
         search_logitech(v, k)
    elif isinstance(v, dict):
         search_logitech(v.values(), k)
