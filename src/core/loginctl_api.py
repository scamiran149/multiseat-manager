import subprocess
import re
import os

def list_seats():
    """Returns a list of all active seats from loginctl."""
    try:
        result = subprocess.run(
            ["loginctl", "list-seats", "--no-legend"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        seats = []
        for line in result.stdout.strip().splitlines():
            parts = line.split()
            if parts:
                seats.append(parts[0])
        return seats
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

def seat_status(seat_name):
    """
    Parses 'loginctl seat-status <seat_name>' and returns a structured dictionary
    of the seat's attached devices.
    """
    try:
        env = dict(os.environ, COLUMNS="4000")
        result = subprocess.run(
            ["loginctl", "seat-status", seat_name], 
            capture_output=True, 
            text=True, 
            check=True,
            env=env
        )
        
        status = {
            "name": seat_name,
            "devices": []
        }
        
        for line in result.stdout.splitlines():
            match = re.search(r'(?:├─|└─|─)\s*(/sys/devices/\S+)', line)
            if match:
                syspath = match.group(1).strip()
                status["devices"].append({
                    "syspath": syspath
                })
        
        return status
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"name": seat_name, "devices": []}

def get_current_assignments():
    """
    Returns a dictionary mapping persistent syspaths to their current non-seat0 seat.
    Example: {"/sys/devices/pci0000:00/...": "seat1"}
    """
    seats = list_seats()
    assignments = {}
    
    for seat in seats:
        if seat == "seat0":
            continue
            
        status = seat_status(seat)
        for dev in status.get("devices", []):
            assignments[dev["syspath"]] = seat
            
    # Also parse 70-multiseat-manager.rules to catch any statically defined mappings
    rules_path = "/etc/udev/rules.d/70-multiseat-manager.rules"
    if os.path.exists(rules_path):
        import re
        with open(rules_path, "r") as f:
            for line in f:
                if 'ENV{ID_SEAT}' in line and 'DEVPATH' in line:
                    devpath_match = re.search(r'DEVPATH=="([^"]+)"', line)
                    seat_match = re.search(r'ENV\{ID_SEAT\}=="([^"]+)"', line)
                    if devpath_match and seat_match:
                        syspath = "/sys" + devpath_match.group(1)
                        if syspath not in assignments:
                            assignments[syspath] = seat_match.group(1)
                            
    return assignments
