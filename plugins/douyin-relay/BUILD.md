# 抖音弹幕中继 — 打包说明

与 [插件系统 — 打包插件](../../blivechat.wiki/插件系统.md) 及 `plugins/msg-logging/msg-logging.spec` 流程一致。

## 前置条件

1. 在 **blivechat 项目根目录** 下操作（以便 `pathex` 能找到 `blcsdk`）。
2. 已安装插件与主程序依赖（含 `aiohttp`、`cachetools`、PyInstaller），例如：

   ```sh
   pip install -r requirements.txt
   pip install -r blcsdk/requirements.txt
   ```

3. **Windows 可执行文件**：建议在 Windows 上打包；在 macOS/Linux 上 PyInstaller 只能生成当前系统的可执行文件（见下文）。

## 打包命令

**路径是相对于「当前工作目录」的。** 下面两种方式任选其一，不要混用。

### 方式 A：在 blivechat 仓库根目录执行（推荐）

```sh
cd /path/to/blivechat
python -m PyInstaller -y plugins/douyin-relay/douyin-relay.spec
```

（若已安装命令：`pyinstaller -y plugins/douyin-relay/douyin-relay.spec`）

### 方式 B：在插件目录 `plugins/douyin-relay/` 下执行

此时 spec 与 `main.py` 就在当前目录，应写**文件名**，不要再带 `plugins/...` 前缀：

```sh
cd /path/to/blivechat/plugins/douyin-relay
python -m PyInstaller -y douyin-relay.spec
```

若在 `plugins/douyin-relay` 里误执行 `python -m PyInstaller -y plugins/douyin-relay/douyin-relay.spec`，会去找子目录 `plugins/douyin-relay/plugins/...`，从而报错 **`Spec file ... not found`**。

### 方式 C：一键从插件目录调用（脚本会 `cd` 到仓库根）

```sh
cd /path/to/blivechat/plugins/douyin-relay
chmod +x build.sh   # 仅首次
./build.sh
```

## 产物

- 目录：`dist/douyin-relay/`（含 `douyin-relay.exe`、`plugin.json`、`data/`、`log/`、`_internal/` 等）。
- 压缩包：`dist/douyin-relay.zip`（由 spec 末尾的 `zipfile` 步骤生成，便于分发）。

将 **整个目录** 或 **解压后的 zip 内容** 放到 `data/plugins/douyin-relay/`，勿只复制单个 exe（缺少 `_internal/` 会导致无法启动）。

## 分发用 plugin.json

仓库中 `plugin.json` 的 `run` 字段为 **`douyin-relay.exe`**，与 PyInstaller 生成的可执行文件名一致。

若本地**不打包、直接跑源码**，可在 `data/plugins/` 下单独放一份开发配置，例如：

```json
{
  "run": "cd ../../../plugins/douyin-relay && python -u main.py"
}
```

（路径按你放置的 `data/plugins/...` 目录调整，参见插件系统文档「让 blivechat 运行开发中的插件」。）

## macOS / Linux

当前 spec 生成的是**当前平台**的可执行文件。若需向 Windows 用户分发 exe，请在 Windows 环境或虚拟机中执行上述打包命令；macOS/Linux 上开发时可继续用 `python -u main.py` 方式运行。
