# Multiseat Manager - Implementation Plan

This document serves as the architectural blueprint for the standalone graphical Systemd `loginctl` multiseat configuration manager. The application is built using a Python and PyQt6 stack.

## Phase 1: The Data Layer
**Objective:** Handle system parsing, hardware detection, alias management, and loginctl integration to build the application's underlying data model.

1. **System Hardware Scraper (`scanner.py`)** 
   - Extract GPU and display topologies by parsing `/sys/class/drm` and `lspci`.
   - Decode EDID data from sysfs to extract human-readable monitor names and manufacturer details.
   - Utilize `evdev` to confidently identify peripherals (keyboards, mice, touchpads) and their human-readable labels.

2. **Loginctl Integration (`loginctl_api.py`)**
   - Execute `loginctl seat-status` and `loginctl list-seats` to retrieve the active multiseat configuration.
   - Parse the output into a structured data model mapping each seat (e.g., `seat0`, `seat1`) to its attached devices.

3. **Persistent Alias Manager (`config.py`)**
   - Implement a JSON-backed configuration manager (`~/.config/multiseat-manager/aliases.json`).
   - Map static, stable hardware identifiers (such as UUIDs, persistent PCI bus addresses, or persistent USB paths) to user-defined aliases (e.g., "Sally's Mouse", "Player 2 Controller").
   - Ensure aliases survive reboots and device re-plugging by relying on physical paths rather than volatile `/dev/input/eventX` numbers.

## Phase 2: Core UI & Wizard
**Objective:** Construct the main PyQt6 interfaces, focusing on an intuitive setup wizard as the primary entry point and an advanced drag-and-drop layout for granular control.

1. **Express Setup Wizard (`wizard.py`)**
   - Implement a PyQt6 `QWizard` as the primary application flow.
   - Guide the user to configure secondary seats (`seat1`, `seat2`, etc.) *first* by prompting them to interactively identify hardware for those seats.
   - The final step must summarize and confirm the remaining unassigned hardware, which naturally defaults to the master seat (`seat0`).

2. **Advanced UI & Seat Columns (`main_window.py` & `seat_column.py`)**
   - A secondary entry point for advanced, granular management.
   - Develop a dynamic, column-based PyQt6 layout.
   - **`seat0` (Master Seat):** Locked to the left side of the UI. It serves as the primary seat holding all unassigned/default devices, and maintains access to the virtual terminal (VT).
   - **Additional Seats (`seat1`, `seat2`, etc.):** Rendered as scrollable, adjacent columns on the right.
   - Implement Qt Drag-and-Drop capability between list widgets so users can visually move devices across seats.
   - Utilize a TreeView grouping model to nest downstream hardware properly (e.g. monitors under GPUs).

## Phase 3: Interactive Workflows
**Objective:** Implement real-time, interactive workflows that help users physically identify which hardware on their desk maps to the entries in the software.

1. **Input Identification Thread (`input_listener.py`)**
   - A background thread utilizing `evdev` to listen for hardware events.
   - **"Click to Identify":** When a user clicks a mouse button or strikes a key on a physical device, the listener fires an event to the main Qt thread.
   - The UI (either within the Wizard or Advanced UI) responds by automatically selecting or assigning the corresponding device.

2. **GPU and Display Visualizer (`display_overlay.py`)**
   - To solve the "Which GPU is this monitor plugged into?" problem.
   - The app spawns a frameless, fully transparent PyQt6 window on every active screen connected to a specific `drm` card.
   - Each window draws a massive, high-contrast identifier (e.g., a number or color) on the overlay, mapping physical displays to `drm` cards visually.

## Phase 4: Execution & Persistence
**Objective:** Apply configurations to the underlying OS, provide robust state management, and integrate into the system environment.

1. **Execution Engine (`executor.py`)**
   - Manage subprocesses to safely execute commands like `pkexec loginctl attach <seat> <sysfs-device>`.
   - Utilize Polkit integration (`pkexec`) to gracefully prompt for the `sudo` privileges required to modify system seat assignments.
   - Provide visual feedback in the UI for success or failure of `loginctl` attachment commands.

2. **System Integration (`desktop_integration.py`)**
   - Generate and manage a standard `.desktop` file to integrate the standalone application into standard Linux desktop environments and settings menus.

3. **State Backup & Restore (`backup.py`)**
   - Allow exporting the entire current multiseat mapping (including custom aliases and device assignments) to a portable config backup file.
   - Allow importing a backup file to instantly construct and queue the `loginctl` commands required to restore a multiseat layout.
