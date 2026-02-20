import os
import re
import subprocess

from .config import ConfigManager

class HardwareScanner:
    def __init__(self, config_manager=None):
        self.config = config_manager or ConfigManager()

    def _get_persistent_id(self, syspath):
        """Generates a stable identifier based on sysfs physical topology."""
        # Syspaths under /sys/devices/ are usually stable across reboots based on the bus topology
        if syspath.startswith("/sys/devices/"):
            return syspath[len("/sys/devices/"):]
        return syspath

    def _decode_edid(self, edid_blob):
        """Extracts human-readable monitor name and manufacturer from an EDID binary blob."""
        if not edid_blob or len(edid_blob) < 128:
            return None
            
        mfg_str = ""
        try:
            mfg_id = (edid_blob[8] << 8) | edid_blob[9]
            c1 = chr(((mfg_id >> 10) & 0x1f) + ord('A') - 1)
            c2 = chr(((mfg_id >> 5) & 0x1f) + ord('A') - 1)
            c3 = chr((mfg_id & 0x1f) + ord('A') - 1)
            mfg = f"{c1}{c2}{c3}"
            
            mfg_map = {
                "SAM": "Samsung", "DEL": "Dell", "AOC": "AOC", "GSM": "LG",
                "ASU": "ASUS", "ACR": "Acer", "BNQ": "BenQ", "HEI": "Hyundai",
                "APP": "Apple", "SNY": "Sony", "PHL": "Philips", "VSC": "ViewSonic",
                "LGO": "LG", "GSM": "LG", "HWP": "HP", "LEN": "Lenovo"
            }
            mfg_str = mfg_map.get(mfg, mfg)
        except Exception:
            pass

        mon_name = None
        for i in range(4):
            offset = 54 + (i * 18)
            if offset + 18 > len(edid_blob):
                break
            descriptor = edid_blob[offset:offset+18]
            if descriptor[0:2] == b'\x00\x00' and descriptor[3] == 0xFC:
                text_data = descriptor[5:].split(b'\x0a')[0]
                mon_name = text_data.decode('ascii', errors='ignore').strip()
                break
                
        if mon_name:
            if mfg_str and not mon_name.lower().startswith(mfg_str.lower()[:3]):
                return f"{mfg_str} {mon_name}"
            return mon_name
        return None

    def _clean_gpu_name(self, vendor_str, device_str):
        """Cleans verbose lspci output into a short, human-readable GPU marketing name."""
        vendor = vendor_str
        v_brackets = re.findall(r'\[(.*?)\]', vendor)
        if v_brackets:
            vendor = v_brackets[-1].split('/')[0].strip()
        else:
            vendor = re.sub(r'(?i)(?:\s*Corporation\s*|\s*Inc\.\s*|,)', '', vendor).strip()
            
        device = device_str
        d_brackets = re.findall(r'\[(.*?)\]', device)
        if d_brackets:
            device = d_brackets[-1].strip()
        else:
            # Clean up generic strings
            patterns = [
                r'(?i)VGA compatible controller:\s*',
                r'(?i)3D controller:\s*',
                r'(?i)\(rev\s+[0-9a-fA-F]+\)\s*$'
            ]
            for p in patterns:
                device = re.sub(p, '', device)
                
        name = f"{vendor} {device}".strip()
        return name or "Unknown GPU"

    def scan_usb_topology(self):
        """
        Scans /sys/bus/usb/devices/ to map USB buses, hubs, and devices.
        Returns a hierarchical dictionary where downstream connections nest under hubs.
        """
        usb_dir = "/sys/bus/usb/devices/"
        devices_map = {}
        
        if not os.path.exists(usb_dir):
            return devices_map

        # Map all devices linearly first
        for item in os.listdir(usb_dir):
            if ":" in item:
                continue
                
            syspath = os.path.realpath(os.path.join(usb_dir, item))
            persistent_id = self._get_persistent_id(syspath)
            
            name = "Unknown USB Device"
            manufacturer = ""
            product = ""
            try:
                with open(os.path.join(syspath, "manufacturer"), "r") as f:
                    manufacturer = f.read().strip()
                with open(os.path.join(syspath, "product"), "r") as f:
                    product = f.read().strip()
                if manufacturer and product:
                    name = f"{manufacturer} {product}"
                elif product:
                    name = product
            except (FileNotFoundError, OSError):
                if item.startswith("usb"):
                    name = f"Root USB Hub ({item})"
            
            is_hub = False
            try:
                with open(os.path.join(syspath, "bDeviceClass"), "r") as f:
                    if f.read().strip() == "09":
                        is_hub = True
            except FileNotFoundError:
                if item.startswith("usb"):
                    is_hub = True
                    
            # Clean up kernel generic strings
            lower_name = name.lower()
            if any(x in lower_name for x in ["linux", "generic", "xhci", "ehci", "uhci", "ohci"]):
                if is_hub and item.startswith("usb"):
                    name = f"Motherboard USB Controller"
                elif is_hub:
                    name = "Generic USB Hub"
                    
            alias = self.config.get_alias(persistent_id)
            
            devices_map[item] = {
                "id": item,
                "syspath": syspath,
                "persistent_id": persistent_id,
                "name": alias if alias else name,
                "is_hub": is_hub,
                "type": "usb",
                "children": []
            }

        # Build hierarchy
        hubs_tree = {}
        for dev_id, dev_info in sorted(devices_map.items()):
            if dev_id.startswith("usb"):
                hubs_tree[dev_id] = dev_info
            else:
                parts = dev_id.rsplit(".", 1)
                if len(parts) > 1:
                    parent_id = parts[0]
                else:
                    parent_id = f"usb{dev_id.split('-')[0]}"
                
                if parent_id in devices_map:
                    devices_map[parent_id]["children"].append(dev_info)
                else:
                    hubs_tree[dev_id] = dev_info
                    
        return hubs_tree

    def scan_graphics(self):
        """
        Scans /sys/class/drm to find GPUs and child DRM monitors.
        Parses `lspci -vmm` to find human-readable GPU names.
        """
        gpus = []
        drm_dir = "/sys/class/drm/"
        if not os.path.exists(drm_dir):
            return gpus

        drm_items = os.listdir(drm_dir)
        for item in drm_items:
            if item.startswith("card") and "-" not in item:
                item_path = os.path.join(drm_dir, item)
                syspath = os.path.realpath(item_path)
                persistent_id = self._get_persistent_id(syspath)
                
                gpu_name = f"GPU ({item})"
                pci_addr = None
                try:
                    with open(os.path.join(item_path, "device", "uevent"), "r") as f:
                        for line in f:
                            if line.startswith("PCI_SLOT_NAME="):
                                pci_addr = line.split("=", 1)[1].strip()
                                break
                except (FileNotFoundError, OSError):
                    pass
                
                if not pci_addr:
                    pci_match = re.search(r'([0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-9a-fA-F])', syspath)
                    if pci_match:
                        pci_addr = pci_match.group(1)

                # Keep track of the core PCI bus path for the GPU to capture child audio/CEC instances later
                gpu_pci_syspath = ""
                if pci_addr:
                    # Strip the final .X function number to just match the device (e.g. 07:00)
                    base_pci = pci_addr.rsplit('.', 1)[0]
                    gpu_pci_syspath = base_pci
                    
                    try:
                        res = subprocess.run(["lspci", "-vmm", "-s", pci_addr], capture_output=True, text=True)
                        vendor = ""
                        device = ""
                        cls = ""
                        for line in res.stdout.splitlines():
                            if line.startswith("Class:"):
                                cls = line.split(":", 1)[1].strip()
                            elif line.startswith("Vendor:"):
                                vendor = line.split(":", 1)[1].strip()
                            elif line.startswith("Device:"):
                                device = line.split(":", 1)[1].strip()
                                
                        if any(x in cls for x in ["VGA", "Display", "3D"]):
                            if vendor or device:
                                gpu_name = self._clean_gpu_name(vendor, device)
                            else:
                                gpu_name = f"GPU PCI {pci_addr}"
                        else:
                            gpu_name = f"GPU PCI {pci_addr}"
                    except Exception:
                        gpu_name = f"GPU PCI {pci_addr}"
                
                alias = self.config.get_alias(persistent_id)
                gpu_info = {
                    "syspath": syspath,
                    "pci_syspath": gpu_pci_syspath, # Use this to trap HDMI sound/CEC
                    "persistent_id": persistent_id,
                    "name": alias if alias else gpu_name,
                    "type": "gpu",
                    "monitors": [],
                    "audio_video": []
                }
                
                for connector in drm_items:
                    if connector.startswith(f"{item}-"):
                        connector_path = os.path.join(drm_dir, connector)
                        status_path = os.path.join(connector_path, "status")
                        try:
                            with open(status_path, "r") as f:
                                status = f.read().strip()
                        except FileNotFoundError:
                            status = "unknown"
                            
                        if status == "connected":
                            monitor_name = f"Display {connector.split('-', 1)[1]}"
                            edid_path = os.path.join(connector_path, "edid")
                            try:
                                with open(edid_path, "rb") as f:
                                    edid_name = self._decode_edid(f.read())
                                    if edid_name:
                                        monitor_name = edid_name
                            except (FileNotFoundError, PermissionError):
                                pass
                                
                            conn_syspath = os.path.realpath(connector_path)
                            conn_persistent_id = self._get_persistent_id(conn_syspath)
                            conn_alias = self.config.get_alias(conn_persistent_id)
                            
                            gpu_info["monitors"].append({
                                "syspath": conn_syspath,
                                "persistent_id": conn_persistent_id,
                                "name": conn_alias if conn_alias else monitor_name,
                                "type": "monitor",
                                "connector": connector.split('-', 1)[1]
                            })
                gpus.append(gpu_info)
        return gpus

    def scan_input_devices(self):
        """
        Scans sysfs input interfaces to map human-readable input devices (Keyboards, Mice, etc).
        Groups multiple event nodes sharing the same physical path into a single logical device.
        """
        grouped_devices = {}
        input_dir = "/sys/class/input"

        try:
            if not os.path.exists(input_dir):
                return []
                
            for ev in os.listdir(input_dir):
                if not ev.startswith("event"):
                    continue
                    
                path = os.path.join(input_dir, ev)
                
                name_path = os.path.join(path, "device", "name")
                caps_ev_path = os.path.join(path, "device", "capabilities", "ev")
                caps_key_path = os.path.join(path, "device", "capabilities", "key")
                phys_path_file = os.path.join(path, "device", "phys")
                
                if not os.path.exists(name_path) or not os.path.exists(caps_ev_path):
                    continue
                    
                with open(name_path, "r") as f:
                    device_name = f.read().strip()
                
                with open(caps_ev_path, "r") as f:
                    ev_bits_hex = f.read().strip()
                ev_bits = int(ev_bits_hex, 16) if ev_bits_hex else 0
                
                # Check capability bits: EV_REL is bit 2, EV_ABS is bit 3
                has_rel = bool((ev_bits >> 2) & 1)
                has_abs = bool((ev_bits >> 3) & 1)
                
                key_count = 0
                if os.path.exists(caps_key_path):
                    with open(caps_key_path, "r") as f:
                        key_str = f.read().strip()
                    for chunk in key_str.split():
                        key_count += bin(int(chunk, 16)).count("1")

                # Strict Input constraints: Must be a mouse (REL/ABS) or have >5 actual keys to be a "Keyboard"
                is_valid = False
                if has_rel or has_abs:
                    is_valid = True
                elif key_count > 5:
                    is_valid = True
                
                name_l = device_name.lower()
                if "hdmi" in name_l or "dp" in name_l or "power button" in name_l:
                    is_valid = False
                    
                if not is_valid:
                    continue
                
                # Try to get the physical path, fallback to the device folder path
                phys_path = ""
                if os.path.exists(phys_path_file):
                    with open(phys_path_file, "r") as f:
                        phys_path = f.read().strip()
                if not phys_path:
                    phys_path = os.path.realpath(os.path.join(path, "device"))
                
                if phys_path not in grouped_devices:
                    grouped_devices[phys_path] = {
                        "device_nodes": [],
                        "names": [],
                        "syspath": "",
                        "persistent_id": "",
                        "has_rel": False,
                        "has_abs": False,
                        "key_count": 0
                    }
                    
                group = grouped_devices[phys_path]
                group["device_nodes"].append(ev)
                group["names"].append(device_name)
                group["has_rel"] = group["has_rel"] or has_rel
                group["has_abs"] = group["has_abs"] or has_abs
                group["key_count"] = max(group["key_count"], key_count)
                
                if not group["syspath"]:
                    try:
                        group["syspath"] = os.path.realpath(path)
                        group["persistent_id"] = self._get_persistent_id(group["syspath"])
                    except OSError:
                        group["syspath"] = path
                        group["persistent_id"] = path
                        
        except Exception as e:
            return [{"error": f"Failed to read sysfs inputs: {e}"}]
            
        # Collapse groups into finalized list
        inputs = []
        for phys_path, group in grouped_devices.items():
            # Pick the shortest, base name (e.g. "Logitech G703" instead of "Logitech G703 System Control")
            best_name = min(group["names"], key=len)
            
            # Clean up known trailing junk
            for suffix in [" System Control", " Consumer Control", " Keyboard", " Mouse", " Wireless Receiver"]:
                if best_name.endswith(suffix) and len(best_name) > len(suffix):
                    best_name = best_name[:-len(suffix)]
            
            alias = self.config.get_alias(group["persistent_id"])
            
            # Infer primarily what this device is
            icon = "🕹️"
            if group["key_count"] > 5:
                icon = "⌨️"
            if group["has_rel"] or group["has_abs"]:
                icon = "🖱️"
                
            final_name = alias if alias else best_name
            
            inputs.append({
                "syspath": group["syspath"],
                "persistent_id": group["persistent_id"],
                "name": f"{icon} {final_name}",
                "type": "input",
                "nodes": group["device_nodes"]
            })
            
        return inputs

    def scan_av_devices(self):
        """Scans ALSA Soundcards and V4L2 Webcams, clustering them by physical hw."""
        av_devices = {}

        # 1. ALSA Soundcards
        if os.path.exists("/sys/class/sound/"):
            for item in os.listdir("/sys/class/sound/"):
                if item.startswith("card"): 
                    syspath = os.path.realpath(f"/sys/class/sound/{item}")
                    persistent_id = self._get_persistent_id(syspath)
                    name = f"Sound Card ({item})"
                    
                    try:
                        with open(os.path.join(syspath, "id"), "r") as f:
                            name = f"Sound ({f.read().strip()})"
                    except OSError:
                        pass
                        
                    eld_monitors = []
                    proc_dir = f"/proc/asound/{item}"
                    if os.path.exists(proc_dir):
                        for f in os.listdir(proc_dir):
                            if f.startswith("eld"):
                                try:
                                    with open(os.path.join(proc_dir, f), "r") as fp:
                                        for line in fp:
                                            if line.startswith("monitor_name"):
                                                parts = line.split(maxsplit=1)
                                                if len(parts) > 1:
                                                    eld_monitors.append(parts[1].strip())
                                except OSError:
                                    pass
                        
                    dev_data = {
                        "syspath": syspath,
                        "persistent_id": persistent_id,
                        "name": self.config.get_alias(persistent_id) or name,
                        "type": "audio",
                        "eld_monitors": eld_monitors,
                        "children": []
                    }
                    if syspath not in av_devices:
                        av_devices[syspath] = dev_data
                        
        # 2. V4L2 Webcams
        if os.path.exists("/sys/class/video4linux/"):
            for item in os.listdir("/sys/class/video4linux/"):
                syspath = os.path.realpath(f"/sys/class/video4linux/{item}")
                persistent_id = self._get_persistent_id(syspath)
                
                name = "Webcam"
                try:
                    with open(os.path.join(syspath, "name"), "r") as f:
                        name = f"Cam ({f.read().strip()})"
                except OSError:
                    pass

                # If this webcam shares a bus parent (like a USB module) with an Audio device, group them!
                parent_syspath = os.path.dirname(syspath) 
                while parent_syspath != "/" and "usb" not in os.path.basename(parent_syspath) and "pci" not in os.path.basename(parent_syspath):
                    parent_syspath = os.path.dirname(parent_syspath)

                matched = False
                for av_path, av_item in av_devices.items():
                    if av_path.startswith(parent_syspath):
                        # It's a combo Audio/Video webcam
                        av_item["name"] = self.config.get_alias(av_item["persistent_id"]) or name.replace("Cam", "Webcam/Mic")
                        av_item["type"] = "camera_mic"
                        matched = True
                        break
                        
                if not matched:
                    av_devices[syspath] = {
                        "syspath": syspath,
                        "persistent_id": persistent_id,
                        "name": self.config.get_alias(persistent_id) or name,
                        "type": "camera",
                        "children": []
                    }
                    
        return list(av_devices.values())

    def full_scan(self):
        """Runs all hardware scans and returns the structured dictionary."""
        usb_tree = self.scan_usb_topology()
        graphics = self.scan_graphics()
        inputs = self.scan_input_devices()
        av_devices = self.scan_av_devices()
        
        # Collapse HDMI/CEC interfaces directly inside their parent GPUs.
        # This removes "HDA NVidia" or "HDA ATI HDMI" soundcards from the main generic lists.
        filtered_av = []
        for av in av_devices:
            trapped = False
            for gpu in graphics:
                # av syspath looks like /sys/class/sound/card1 -> /sys/devices/pci0000:00/.../0000:07:00.1/...
                # gpu pci_syspath is "0000:07:00"
                if gpu.get("pci_syspath") and gpu["pci_syspath"] in av.get("syspath", ""):
                    
                    # Rename generic HDMI Audio
                    if any(x in av["name"].upper() for x in ["HDMI", "DP", "GENERIC", "HDA"]):
                        av["name"] = "Monitor Audio Output"

                    # Try to pair with a specific monitor based on ELD
                    paired = False
                    for mon in gpu["monitors"]:
                        mon_name_l = mon["name"].lower()
                        if any(e.lower() in mon_name_l or mon_name_l in e.lower() for e in av.get("eld_monitors", [])):
                            if "audio_video" not in mon:
                                mon["audio_video"] = []
                            mon["audio_video"].append(av)
                            paired = True
                            break
                    
                    if not paired:
                        # Fallback: if there's only 1 monitor, just pair it
                        if len(gpu["monitors"]) == 1:
                            mon = gpu["monitors"][0]
                            if "audio_video" not in mon:
                                mon["audio_video"] = []
                            mon["audio_video"].append(av)
                            paired = True
                    
                    if not paired:
                        gpu["audio_video"].append(av)
                        
                    trapped = True
                    break
            if not trapped:
                filtered_av.append(av)
                
        # Do the same check to hide generic USB nodes containing these interfaces
        combined_syspaths = [inp.get("syspath", "") for inp in inputs if "syspath" in inp] + \
                            [av.get("syspath", "") for av in av_devices if "syspath" in av]
        
        def _hide_used_usb(nodes):
            for node in nodes:
                node_sys = node.get("syspath", "")
                if any(ext_sys.startswith(node_sys) for ext_sys in combined_syspaths):
                    node["hidden_by_input"] = True
                if "children" in node:
                    _hide_used_usb(node["children"])
                    
        _hide_used_usb(usb_tree.values())
        
        return {
            "usb": usb_tree,
            "graphics": graphics,
            "inputs": inputs,
            "av": filtered_av
        }
