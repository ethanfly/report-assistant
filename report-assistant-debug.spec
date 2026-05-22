# -*- mode: python ; coding: utf-8 -*-
# 调试版本：带控制台窗口，能直接看到 Python stdout/stderr，
# 用于排查 windowed 模式下看不见的卡死/崩溃。
# 用法：pyinstaller --noconfirm report-assistant-debug.spec
#       双击 dist/report-assistant-debug/report-assistant-debug.exe
from PyInstaller.utils.hooks import collect_all

datas = [('report_assistant/desktop/assets', 'report_assistant/desktop/assets')]
binaries = []
hiddenimports = []
tmp_ret = collect_all('report_assistant')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

a = Analysis(
    ['entry.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='report-assistant-debug',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # 关键：保留控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['report_assistant\\desktop\\assets\\logo.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='report-assistant-debug',
)
