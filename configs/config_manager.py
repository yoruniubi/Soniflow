import json
import os
import logging
import sys
class ConfigManager:
    def __init__(self, config_file_relative_path='configs/user_config.json'):
        self.config_file_relative_path = config_file_relative_path
        self.config_file = self._resolve_path(config_file_relative_path)
        self.config = self._load_config()

    def _resolve_path(self, relative_path):
        """ Resolves the absolute path for resources, compatible with PyInstaller. """
        if hasattr(sys, '_MEIPASS'):
            # When bundled, resources are in the temporary directory sys._MEIPASS
            base_path = sys._MEIPASS
        else:
            # In development, use the current directory's relative path
            base_path = os.path.abspath(".")
        return os.path.normpath(os.path.join(base_path, relative_path))

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

config_manager = ConfigManager()  # Instantiate the ConfigManager to be used throughout the application

# Instantiate the ConfigManager to be used throughout the application