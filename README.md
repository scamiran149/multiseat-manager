# Multiseat Manager

Multiseat Manager is a graphical Qt desktop application for Linux that provides an intuitive interface for managing `systemd-loginctl` device assignments. It allows you to easily map GPUs, monitors, USB hubs, and input devices to specific seats to create multi-monitor, multi-user environments on a single physical machine.

## Features

- **Rootless GUI:** The main interface runs unprivileged, only prompting for `pkexec` authorization when absolutely necessary (e.g., listening for raw `/dev/input/` events or applying structural changes).
- **Express Setup Wizard:** A simple step-by-step wizard to quickly assign a monitor, keyboard, and mouse to a new seat.
- **Advanced Manual Setup:** A powerful drag-and-drop tree interface for intricate USB and PCI mapping.
- **Review Before Apply:** All generated configurations are staged locally in the app directory for your review as `udev` rules and a batch shell script before committing them to your system.
- **Save & Load:** Export complex hardware topologies to simple JSON files and restore them dynamically.

## Screenshots

### Launcher
![Launcher](docs/launcher.png)

### Express Setup Wizard
![Wizard](docs/wizard.png)

### Advanced Manual Setup
![Advanced UI](docs/advanced_ui.png)

## Installation

### From Source
1. Clone the repository: `git clone https://github.com/USERNAME/multiseat-manager.git`
2. Run the bootstrapper: `./launch.sh` 
*(This will automatically configure a python virtual environment, install dependencies, and launch the UI.)*

### Optional Desktop Integration
If you wish to manage Multiseat Manager from your native desktop environment's application menu:
```bash
make install
```

## Review Workflow

For safety, **Multiseat Manager** never modifies your live system state immediately.
When you click **Apply Configuration**, the tool generates the following in a local `staging/` directory:
1. `apply_config.sh`: Precise `loginctl attach` commands specifically diffed against your current session.
2. `70-multiseat-manager.rules`: Heavily commented persistent `udev` device rules matching your assignments.

A review dialog will appear allowing you to inspect these exact files before firing off `pkexec` to install them into `/etc/udev/rules.d/`.

## Legal
Licensed under the MIT License.
