"""桌面端图标资源。运行 generate_logo 生成 PNG/ICO。"""
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent


def icon_path(name: str = "logo.png") -> Path:
    return ASSETS_DIR / name
