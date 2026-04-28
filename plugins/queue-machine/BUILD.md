# 直播排队机 — 打包说明

与 [插件系统 — 打包插件](../../blivechat.wiki/插件系统.md) 及 `plugins/msg-logging/msg-logging.spec` 流程一致。

## 前置条件

1. 在 **blivechat 仓库根目录** 下操作（或从本目录执行 `./build.sh`，脚本会自行 `cd` 到根目录）。**当前工作目录必须是 blivechat 根**，否则 PyInstaller 会把 `dist/`、`build/` 写到错误位置。
2. 已安装主工程 / 插件 SDK 依赖（含 `aiohttp`、PyInstaller），例如已执行过仓库要求的 `pip install` / 虚拟环境安装。

## 打包命令

在仓库根目录：

```bash
python -m PyInstaller -y plugins/queue-machine/queue-machine.spec
```

或在本插件目录：

```bash
./build.sh
```

**注意**：若在 `plugins/queue-machine` 下误执行 `python -m PyInstaller -y plugins/queue-machine/queue-machine.spec`（带 `plugins/...` 前缀），会解析错误路径并报 **Spec file ... not found**。在子目录内应使用：

```bash
python -m PyInstaller -y queue-machine.spec
```

## 产物

- 目录：`dist/queue-machine/`（含可执行文件、`web/` 静态资源、`plugin.json`、`data/`、`log/` 等）。
- 压缩包：`dist/queue-machine.zip`（由 spec 末尾自动生成，便于分发）。

将 **`dist/queue-machine/` 整目录** 复制到 `data/plugins/queue-machine/`（或把 zip 解压到该路径），并保证 `plugin.json` 中 `"run": "queue-machine.exe"`（Windows）与产物名称一致。

## 平台说明

PyInstaller **只能在当前系统上生成对应平台的可执行文件**。需要向 Windows 用户分发 `.exe` 时，请在 **Windows**（或对应虚拟机）上执行上述命令；在 macOS 上构建得到的是无后缀的 `queue-machine`，需在 `plugin.json` 的 `run` 中写实际文件名（例如 `"run": "queue-machine"`）。

## 源码调试（不打包）

可将 `data/plugins/queue-machine/plugin.json` 的 `run` 改为本机 Python，例如：

```json
"run": "python -u main.py"
```

并在含 `main.py` 的插件目录下启动（或配合 `cd` 与绝对路径，见插件系统文档）。
