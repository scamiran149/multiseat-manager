import os
import json

class ConfigManager:
    """Manages multiseat aliases stored in a JSON configuration file."""
    
    DEFAULT_SYSTEM_PATH = "/etc/multiseat-manager/aliases.json"
    DEFAULT_USER_PATH = "~/.config/multiseat-manager/aliases.json"

    def __init__(self, config_path=None):
        self.system_path = self.DEFAULT_SYSTEM_PATH
        self.user_path = os.path.expanduser(self.DEFAULT_USER_PATH)
        
        # If no path is provided, try system first, then user
        if config_path:
            self.config_path = os.path.expanduser(config_path)
        else:
            self.config_path = self.system_path
            
        self.aliases = self._load()
        
        # Migrate from old user path if we are using the system path and it's empty
        if not config_path and self.config_path == self.system_path and not self.aliases:
            self._migrate_from_user()

    def _load(self):
        """Loads aliases from the JSON file. Tries system, then user if system is missing."""
        paths_to_try = [self.config_path]
        if self.config_path != self.user_path:
            paths_to_try.append(self.user_path)

        for path in paths_to_try:
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        return json.load(f)
                except (json.JSONDecodeError, OSError):
                    continue
        return {}

    def _migrate_from_user(self):
        """Attempts to migrate aliases from user-local config to system config."""
        if os.path.exists(self.user_path):
            try:
                with open(self.user_path, "r") as f:
                    user_aliases = json.load(f)
                if user_aliases:
                    self.aliases.update(user_aliases)
                    # We don't save yet; we'll save to the best available path on the next set_alias or manual save()
            except (json.JSONDecodeError, OSError):
                pass

    def save(self):
        """Saves current aliases to the JSON file. Falls back to user path if system path is read-only."""
        paths_to_try = [self.config_path]
        if self.config_path != self.user_path:
            paths_to_try.append(self.user_path)

        for path in paths_to_try:
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w") as f:
                    json.dump(self.aliases, f, indent=4)
                return # Success
            except OSError:
                continue
        print(f"Error: Could not save config to any of {paths_to_try}")

    def get_alias(self, persistent_id, default=None):
        """Retrieves user-defined alias for a given persistent hardware ID."""
        return self.aliases.get(persistent_id, default)

    def set_alias(self, persistent_id, alias):
        """Sets or updates a user-defined alias for a hardware ID and saves."""
        if alias is None or alias.strip() == "":
            self.aliases.pop(persistent_id, None)
        else:
            self.aliases[persistent_id] = alias
        self.save()
