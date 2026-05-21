# -*- mode: python ; coding: utf-8 -*-
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
    a.binaries,
    a.datas,
    [],
    name='report-assistant',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX 显著拖慢首次启动（解压 + 杀软扫描），关闭以提速
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['report_assistant\\desktop\\assets\\logo.ico'],
)
