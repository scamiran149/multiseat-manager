import os
for ev in os.listdir("/sys/class/input"):
    if not ev.startswith("event"): continue
    path = f"/sys/class/input/{ev}"
    name_path = f"{path}/device/name"
    caps_ev_path = f"{path}/device/capabilities/ev"
    caps_key_path = f"{path}/device/capabilities/key"
    name = "Unknown"
    if os.path.exists(name_path):
        with open(name_path) as f: name = f.read().strip()
    ev_bits = ""
    if os.path.exists(caps_ev_path):
        with open(caps_ev_path) as f: ev_bits = f.read().strip()
    key_bits = ""
    if os.path.exists(caps_key_path):
        with open(caps_key_path) as f: key_bits = f.read().strip()
    print(f"{ev}: {name} (ev: {ev_bits}, key: {key_bits})")
