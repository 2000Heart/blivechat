# -*- mode: python ; coding: utf-8 -*-
import os
import subprocess
import sys
import typing

if typing.TYPE_CHECKING:
    from PyInstaller.building.api import COLLECT, EXE, PYZ
    from PyInstaller.building.build_main import Analysis

    SPECPATH = ''
    DISTPATH = ''

# 可执行文件名、dist 子目录名（分发时 plugin.json 的 run 需与此一致，Windows 为 data-analytics.exe）
NAME = 'data-analytics'
PYTHONPATH = [
    os.path.join(SPECPATH, '..', '..'),
]
DATAS = [
    ('plugin.json', '.'),
    ('web', 'web'),
    ('log/.gitkeep', 'log'),
    ('data/.gitkeep', 'data'),
]

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=PYTHONPATH,
    binaries=[],
    datas=DATAS,
    hiddenimports=[
        'aiohttp',
        'aiohttp.client',
        'multidict',
        'yarl',
        'frozenlist',
        'aiosignal',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory='.',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=NAME,
)

print('Start to package')
subprocess.run([sys.executable, '-m', 'zipfile', '-c', NAME + '.zip', NAME], cwd=DISTPATH)
