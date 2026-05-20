import json
from pathlib import Path

CONFIG_PATH = Path('config/settings.json')
DEFAULTS = {
    'remember_password': False,
    'auto_login': False,
    'username': '',
    'password': '',
    'theme': 'light',
    'start_with_windows': False,
    'minimize_to_tray': True,
    'default_save_path': str(Path.cwd()),
    'api_key': ''
}


def load_config():
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        save_config(DEFAULTS)
        return DEFAULTS.copy()
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    except Exception:
        data = {}
    merged = DEFAULTS.copy()
    merged.update(data)
    return merged


def save_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
