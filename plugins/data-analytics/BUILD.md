# 数据分析插件 — 打包说明

与 [插件系统 — 打包插件](../../blivechat.wiki/插件系统.md) 及 `plugins/msg-logging/msg-logging.spec` 流程一致。

## 前置条件

1. 在 **blivechat 项目根目录** 下操作（或从本目录执行 `./build.sh`，脚本会自行 `cd` 到根目录），以便 `pathex` 能找到 `blcsdk`。
2. 已安装插件依赖与 PyInstaller，例如：

   ```sh
   python -m pip install -r plugins/data-analytics/requirements.txt
   python -m pip install -r blcsdk/requirements.txt
   python -m pip install pyinstaller
   ```

3. **构建看板前端**（生成 `web/dist`，打包必需）：

   ```sh
   cd plugins/data-analytics/dashboard
   npm install
   npm run build
   ```

4. **Windows 可执行文件**：建议在 Windows 上打包；在 macOS/Linux 上 PyInstaller 只能生成当前系统的可执行文件（见下文）。

## 打包命令

**路径相对于当前工作目录。** 任选其一，不要混用路径写法。

### 方式 A：在 blivechat 仓库根目录执行（推荐）

```sh
cd /path/to/blivechat
python -m PyInstaller -y plugins/data-analytics/data-analytics.spec
```

（若已安装命令：`pyinstaller -y plugins/data-analytics/data-analytics.spec`）

### 方式 B：在插件目录 `plugins/data-analytics/` 下执行

此时 spec 与 `main.py` 就在当前目录，应写**文件名**，不要再带 `plugins/...` 前缀：

```sh
cd /path/to/blivechat/plugins/data-analytics
python -m PyInstaller -y data-analytics.spec
```

若在 `plugins/data-analytics` 里误执行 `python -m PyInstaller -y plugins/data-analytics/data-analytics.spec`，会去找子目录 `plugins/data-analytics/plugins/...`，从而报错 **`Spec file ... not found`**。

### 方式 C：一键从插件目录调用（脚本会 `cd` 到仓库根）

```sh
cd /path/to/blivechat/plugins/data-analytics
chmod +x build.sh   # 仅首次
./build.sh
```

## 产物

- 目录：`dist/data-analytics/`（含可执行文件、`web/` 静态资源、`plugin.json`、`data/`、`log/`、`_internal/` 等）。
- 压缩包：`dist/data-analytics.zip`（由 spec 末尾的 `zipfile` 步骤自动生成，便于分发）。

将 **`dist/data-analytics/` 整目录** 复制到 `data/plugins/data-analytics/`（或把 zip 解压到该路径）。**勿只复制单个 exe**（缺少 `_internal/` 会导致无法启动）。

分发用的 `plugin.json` 中 `"run"` 应与产物可执行文件名一致，例如 Windows：`"run": "data-analytics.exe"`。

## 平台说明

PyInstaller **只能在当前系统上生成对应平台的可执行文件**。若需向 Windows 用户分发 `.exe`，请在 **Windows**（或对应虚拟机）上执行上述命令；在 macOS 上构建得到的是无后缀的 `data-analytics`，需在 `plugin.json` 的 `run` 中写实际文件名（例如 `"run": "data-analytics"`）。

## 源码调试（不打包）

可将 `data/plugins/data-analytics/plugin.json` 的 `run` 改为本机 Python，例如：

```json
"run": "python -u main.py"
```

并在含 `main.py` 的插件目录下启动（或配合 `cd` 与绝对路径，见插件系统文档）。

## 常见问题

**Q: 打包后看板 404 或静态资源缺失**  
A: 请先执行 `dashboard` 下的 `npm run build`，确保存在 `plugins/data-analytics/web/dist/`（内含 `index.html` 等）后再打包。

**Q: 提示找不到 blcsdk**  
A: 必须在 blivechat **仓库根**执行方式 A / `./build.sh`，或在插件目录用方式 B；勿在错误 cwd 下带错 spec 路径。

**Q: 不想打包，直接用 Python**  
A: 将 `plugin.json` 的 `run` 设为 `python -u main.py`（或指向本机解释器绝对路径），从项目根启动 blivechat 即可。
