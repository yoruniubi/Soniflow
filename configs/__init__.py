import json
import os
import logging

class ConfigManager:
    def __init__(self, config_file='configs/user_config.json'):
        self.config_file = config_file
        self.config = self._load_config()

    def _load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logging.error(f"Error decoding JSON from {self.config_file}: {e}")
                return {}
            except Exception as e:
                logging.error(f"Error loading config file {self.config_file}: {e}")
                return {}
        return {}

    def _save_config(self):
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Error saving config file {self.config_file}: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self._save_config()

# Instantiate the ConfigManager to be used throughout the application
config_manager = ConfigManager()
