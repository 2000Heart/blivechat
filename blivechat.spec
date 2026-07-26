# -*- mode: python ; coding: utf-8 -*-
# 在仓库根目录执行: python -m PyInstaller -y blivechat.spec
# 需要: Python 3.12+、已构建 frontend/dist、已初始化 blivedm 子模块、在 Windows 上构建以生成 .exe
import os
import subprocess
import sys
import typing

if typing.TYPE_CHECKING:
    from PyInstaller.building.api import COLLECT, EXE, PYZ
    from PyInstaller.building.build_main import Analysis

    SPECPATH = ''
    DISTPATH = ''


def _data_src_dest_pairs(repo_root: str) -> list:
    """PyInstaller 6 的 Analysis(datas=...) 只接受 (源路径, 目标相对目录) 二元组，不能用 Tree（Tree 展开为三元组 TOC）。"""
    data_root = os.path.join(repo_root, 'data')
    if not os.path.isdir(data_root):
        return []
    out: list = []
    skip_names = {'plugins'}
    for name in sorted(os.listdir(data_root)):
        if name in skip_names or name.endswith('.db'):
            continue
        src = os.path.join(data_root, name)
        if os.path.isfile(src):
            out.append((src, 'data'))
        elif os.path.isdir(src):
            out.append((src, os.path.join('data', name)))
    return out


NAME = 'blivechat'
ROOT = SPECPATH
BLIVEDM_PKG = os.path.join(ROOT, 'blivedm', 'blivedm')
if not os.path.isfile(os.path.join(BLIVEDM_PKG, '__init__.py')):
    raise SystemExit(
        '未找到 blivedm 子模块。请先执行: git submodule update --init --recursive'
    )
FRONTEND_DIST = os.path.join(ROOT, 'frontend', 'dist')
if not os.path.isfile(os.path.join(FRONTEND_DIST, 'index.html')):
    raise SystemExit(
        '未找到 frontend/dist/index.html。请先执行: cd frontend && npm i && npm run build'
    )

PLUGIN_KEEP = os.path.join(ROOT, 'data', 'plugins', '.gitkeep')
DATAS = [
    (FRONTEND_DIST, os.path.join('frontend', 'dist')),
    (os.path.join(ROOT, 'log'), 'log'),
]
DATAS.extend(_data_src_dest_pairs(ROOT))
if os.path.isfile(PLUGIN_KEEP):
    DATAS.append((PLUGIN_KEEP, os.path.join('data', 'plugins')))

for extra in ('LICENSE', 'README.md'):
    p = os.path.join(ROOT, extra)
    if os.path.isfile(p):
        DATAS.append((p, '.'))

PYTHONPATH = [ROOT, os.path.join(ROOT, 'blivedm'), os.path.join(ROOT, 'blcsdk')]

try:
    from PyInstaller.utils.hooks import collect_submodules

    _hidden = collect_submodules('blivedm')
except Exception:
    _hidden = []

_extra_hidden = [
    'sqlalchemy.dialects.sqlite',
    'aiohttp',
    'multidict',
    'yarl',
    'frozenlist',
    'aiosignal',
    'charset_normalizer',
    'certifi',
    'Crypto',
    'Crypto.Cipher',
    'Crypto.Cipher.AES',
    'Crypto.Util.Padding',
    'circuitbreaker',
    'cachetools',
    'greenlet',
    'pure_protobuf',
    'pure_protobuf.message',
    'pure_protobuf.annotations',
    'brotli',
    'blcsdk',
    'blcsdk.api',
    'blcsdk.client',
    'blcsdk.exc',
    'blcsdk.handlers',
    'blcsdk.models',
]

hiddenimports = list(dict.fromkeys(_hidden + _extra_hidden))

block_cipher = None

a = Analysis(
    [os.path.join(ROOT, 'main.py')],
    pathex=PYTHONPATH,
    binaries=[],
    datas=DATAS,
    hiddenimports=hiddenimports,
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

_exe_common = dict(
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
)

try:
    _pvi = tuple(int(x) for x in __import__('PyInstaller').__version__.split('.')[:2])
except Exception:
    _pvi = (5, 0)

if _pvi >= (6, 0):
    exe = EXE(
        pyz,
        a.scripts,
        [],
        **_exe_common,
        contents_directory='.',
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        **_exe_common,
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

print('Start to zip distribution')
subprocess.run(
    [sys.executable, '-m', 'zipfile', '-c', NAME + '.zip', NAME],
    cwd=DISTPATH,
    check=True,
)
