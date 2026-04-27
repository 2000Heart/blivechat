# -*- mode: python ; coding: utf-8 -*-
import os
import subprocess
import sys

# exe 文件名、打包目录名（与 plugin.json 中 run 字段一致）
NAME = 'douyin-relay'
# 模块搜索路径：blivechat 项目根，以便找到 blcsdk
PYTHONPATH = [
    os.path.join(SPECPATH, '..', '..'),
]
# 随 exe 分发的数据文件
DATAS = [
    ('plugin.json', '.'),
    ('LICENSE', '.'),
    ('data/config.example.ini', 'data'),
    ('log/.gitkeep', 'log'),
    # sidecar 运行所需的 dycast 项目（含 node_modules / 可选 .node 便携 Node）
    # Analysis.datas 仅接受 (src, dest) 二元组，这里直接打包整个目录。
    ('dycast', 'dycast'),
]

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=PYTHONPATH,
    binaries=[],
    datas=DATAS,
    hiddenimports=[
        'aiohttp',
        'cachetools',
        'multidict',
        'yarl',
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
