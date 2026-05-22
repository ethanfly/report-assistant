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

# 使用 onedir 模式（COLLECT）：把依赖摊到一个目录里，避免每次启动
# 都把 75MB 解到 %TEMP%。单 exe 模式下首屏要等 5-10s 解压，
# Windows 期间会把窗口标为"未响应"。
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # 二进制留给 COLLECT 阶段
    name='report-assistant',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
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
    name='report-assistant',
)
