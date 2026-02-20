import os
import json

class ConfigManager:
    """Manages multiseat aliases stored in a JSON configuration file."""
    
    def __init__(self, config_path="~/.config/multiseat-manager/aliases.json"):
        self.config_path = os.path.expanduser(config_path)
        self.aliases = self._load()

    def _load(self):
        """Loads aliases from the JSON file. Creates an empty dict if not found."""
        if not os.path.exists(self.config_path):
            return {}
        try:
            with open(self.config_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self):
        """Saves current aliases to the JSON file."""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        try:
            with open(self.config_path, "w") as f:
                json.dump(self.aliases, f, indent=4)
        except OSError as e:
            print(f"Error saving config: {e}")

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
