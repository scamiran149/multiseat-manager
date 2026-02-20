#!/usr/bin/env bash

# This script installs the pre-compiled Multiseat Manager binary to /opt/
# and generates a system-wide desktop integration file.

if [ "$EUID" -ne 0 ]; then
  echo "Please run this installer with sudo or pkexec."
  exit 1
fi

echo "Installing Multiseat Manager to /opt/multiseat-manager..."

INSTALL_DIR="/opt/multiseat-manager"
BIN_DIR="/usr/local/bin"

mkdir -p "$INSTALL_DIR"
cp -f dist/multiseat-manager "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/multiseat-manager"

# Link to path
ln -sf "$INSTALL_DIR/multiseat-manager" "$BIN_DIR/multiseat-manager"

echo "Creating Desktop Entry..."
cat << 'EOF' > /usr/share/applications/multiseat-manager.desktop
[Desktop Entry]
Name=Multiseat Manager
Comment=Configure loginctl multiseat hardware assignments dynamically.
Exec=/usr/local/bin/multiseat-manager
Icon=preferences-desktop-peripherals
Terminal=false
Type=Application
Categories=Qt;KDE;Settings;HardwareSettings;System;
Keywords=multiseat;loginctl;seat;hardware;usb;gpu;
EOF

chmod +x /usr/share/applications/multiseat-manager.desktop
update-desktop-database /usr/share/applications/ > /dev/null 2>&1

echo "Installation Complete!"
echo "You can now launch 'Multiseat Manager' from your application menu."
