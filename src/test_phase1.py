import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
from src.core.scanner import HardwareScanner
from src.core.loginctl_api import list_seats, seat_status
from src.core.config import ConfigManager

def main():
    print("--- Testing Config Manager ---")
    config_path = "/tmp/test_aliases.json"
    config = ConfigManager(config_path)
    config.set_alias("test-id-1234", "My Test Alias")
    print(f"Saved alias: test-id-1234 -> {config.get_alias('test-id-1234')}")

    print("\n--- Testing loginctl API ---")
    seats = list_seats()
    print(f"Available seats: {seats}")
    if seats:
        status = seat_status(seats[0])
        print(f"Status for {seats[0]}: {json.dumps(status, indent=4)[:300]}...")

    print("\n--- Testing Hardware Scanner ---")
    scanner = HardwareScanner(config)
    scan_results = scanner.full_scan()
    print(json.dumps(scan_results, indent=4))

if __name__ == "__main__":
    main()
