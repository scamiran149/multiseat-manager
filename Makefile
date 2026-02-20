.PHONY: install uninstall clean

install:
	@echo "Installing Multiseat Manager shortcut..."
	@.venv/bin/python3 -c "import sys; sys.path.insert(0, '.'); from src.core.desktop_integration import install_desktop_file; install_desktop_file()"
	@echo "Installation complete. You can now launch 'Multiseat Manager' from your application menu."

uninstall:
	@echo "Removing Multiseat Manager shortcut..."
	@rm -f ~/.local/share/applications/multiseat-manager.desktop
	@update-desktop-database ~/.local/share/applications/ > /dev/null 2>&1
	@echo "Uninstallation complete."

clean:
	@echo "Cleaning up temporary and staging files..."
	@rm -rf staging/
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@echo "Cleanup complete."
