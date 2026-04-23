# Windows 可执行文件（blivechat.exe）构建说明

PyInstaller **只能在当前操作系统上生成对应平台的可执行文件**，因此主程序 exe 需要在 **64 位 Windows** 上构建（与官方 Release 一致）。macOS / Linux 上可写好 spec 与脚本，但无法直接得到 `.exe`。

## 前置条件

1. 安装 [Python 3.12+](https://www.python.org/downloads/windows/)（与项目要求一致），并勾选将 Python 加入 PATH。
2. 安装 [Node.js](https://nodejs.org/)（用于构建前端）。
3. 安装 [Git](https://git-scm.com/download/win)（用于拉取子模块）。

## 一键构建

在仓库根目录双击或在 `cmd` / PowerShell 中执行：

```bat
build_exe.bat
```

脚本会依次：初始化 `blivedm` 子模块、按需执行 `frontend` 的 `npm install` 与 `npm run build`、安装 `requirements-windows-build.txt`、运行 `PyInstaller`。

## 手动步骤（与脚本等价）

```bat
git submodule update --init --recursive
cd frontend
npm install
npm run build
cd ..
python -m pip install -r requirements-windows-build.txt
python -m PyInstaller -y blivechat.spec
```

## 产物位置

| 产物 | 路径 |
|------|------|
| 目录（与官方 zip 解压后类似：exe + dll + `data` / `frontend` 等） | `dist\blivechat\` |
| 便于分发的 zip | `dist\blivechat.zip` |

`data\plugins` 在打包时会排除本地已安装的插件目录，仅保留空的 `data\plugins`（含 `.gitkeep`），避免把开发机上的插件二进制打进包内。

## 与官方 zip 的差异说明

- 使用 **PyInstaller 6+** 时，spec 中设置了 `contents_directory='.'`，得到与常见官方包类似的**扁平** onedir 布局（无 `_internal` 子目录）。
- 若使用较旧 PyInstaller 5.x，布局可能略有不同，但冻结运行时路径已通过 `config.py` 中的 `sys.frozen` 处理，数据与前端仍相对 `blivechat.exe` 所在目录解析。

## B 站商店版文件名

若需要与 B 站特供版一致的可执行文件名，在打包完成后将 `dist\blivechat\blivechat.exe` 复制或重命名为 `start.exe` 即可（与官方说明一致）。
