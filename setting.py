import json
import os

SETTINGS_FILE = 'user_config.json'

def get_settings_path():
    """Returns the absolute path to the settings file."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), SETTINGS_FILE)

def load_settings():
    """Loads settings from a JSON file. Returns default settings if file not found or invalid."""
    settings_path = get_settings_path()
    default_settings = get_default_settings()
    
    if os.path.exists(settings_path):
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                full_config = json.load(f)
                # Return the 'user_config' part, or default if not found
                return full_config.get('user_config', default_settings)
        except json.JSONDecodeError:
            print(f"Error decoding JSON from {settings_path}. Returning default settings.")
            return default_settings
    return default_settings

def save_settings(settings_data):
    """Saves settings to a JSON file under the 'user_config' key."""
    settings_path = get_settings_path()
    
    # Load existing full config to preserve other keys if they exist
    full_config = {}
    if os.path.exists(settings_path):
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                full_config = json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Existing {settings_path} is invalid JSON. Overwriting.")
            full_config = {} # Start fresh if existing file is corrupt

    full_config['user_config'] = settings_data # Update the user_config key
    
    try:
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(full_config, f, indent=4, ensure_ascii=False)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_default_settings():
    """Returns a dictionary of default application settings for 'user_config'."""
    return {
        "theme": "浅色模式", # Default to light mode
        "language": "zh-CN",
        "notifications": True,
        "auto_save": False,
        "recent_files": [],
        "defaultOutput": os.path.join(os.getcwd(), 'output') # Default to 'output' folder in CWD
    }

if __name__ == "__main__":
    # Example usage:
    settings = load_settings()
    print("Loaded settings:", settings)

    # Modify a setting
    settings['defaultOutput'] = 'C:\\Users\\NewOutput'
    settings['theme'] = 'dark'
    save_settings(settings)
    print("Settings saved.")

    # Load again to verify
    updated_settings = load_settings()
    print("Updated settings:", updated_settings)
