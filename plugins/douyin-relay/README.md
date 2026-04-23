# 抖音弹幕中继（douyin-relay）

将 [dycast](https://github.com/skmcj/dycast) 通过 WebSocket 转发的弹幕注入到 blivechat，与 B 站弹幕同屏显示（前端模板如 `liquid-glass` 无需修改）。

## 安装位置

blivechat 只扫描 **`data/plugins/<插件ID>/`** 目录（见 `services/plugin.py`）。

请把本目录复制或软链到：

```text
<blivechat 根目录>/data/plugins/douyin-relay/
```

从本仓库开发时，可在 `data/plugins` 下执行：

```bash
ln -s ../../plugins/douyin-relay douyin-relay
```

### 源码调试（不打包 exe）

默认 `plugin.json` 的 `run` 为 **`douyin-relay.exe`**（与 PyInstaller 产物一致）。若要在未打包时直接跑 Python，请按 [插件系统文档](../../blivechat.wiki/插件系统.md) 在 `data/plugins/` 中使用独立目录或修改 `run`，例如：

```json
"run": "cd ../../../plugins/douyin-relay && python -u main.py"
```

### 打包分发

见同目录下的 [BUILD.md](BUILD.md)。必须在 **blivechat 仓库根目录** 执行（或在 `plugins/douyin-relay` 下执行 `./build.sh` / `PyInstaller -y douyin-relay.spec`），详见 [BUILD.md](BUILD.md)。示例：

```sh
cd /path/to/blivechat
python -m PyInstaller -y plugins/douyin-relay/douyin-relay.spec
```

将 `dist/douyin-relay.zip` 解压到 `data/plugins/douyin-relay/` 即可。

## 配置

1. 将 `data/config.example.ini` 复制为 `data/config.ini`（与示例同目录）。
2. 按需修改 `[relay]` 中的 `listen_host`、`listen_port`、`ws_path`。
3. 默认监听：`ws://127.0.0.1:18765/`（路径为 `/` 时，dycast 填写 `ws://127.0.0.1:18765` 或 `ws://127.0.0.1:18765/` 均可）。

## 使用步骤

1. 启动 blivechat，在插件管理中启用 **抖音弹幕中继**（首次需在 `data/plugins/douyin-relay/plugin.json` 中把 `enabled` 改为 `true`，或通过管理界面开启）。
2. 在插件列表中点击本插件的 **管理**，在弹出窗口中复制 **WebSocket 地址**（与 `data/config.ini` 中 `[relay]` 的监听配置一致）。
3. 确认本插件日志中出现：`抖音中继已启动，请在 dycast 填写 ws://...`。
4. 打开 dycast，连接抖音房间后，在 **WS地址** 填入上一步的 WebSocket URL，点击 **转发**。
5. 打开 blivechat 房间页与 OBS 浏览器源，应能看到带 `[抖音]` 前缀的弹幕。

## 数据格式说明

与 dycast 行为一致：

- 转发连接建立后，会先推送一条 **直播间信息 JSON 对象**（仅记录日志，不注入）。
- 之后每条为 **弹幕消息数组** 的 JSON 序列化结果。

## 依赖

与主项目一致，需已安装 `aiohttp`、`cachetools`（见主仓库 `requirements.txt` / `blivedm/requirements.txt`）。

## 故障排查

- 无法连接：检查防火墙、`listen_host` 是否应用 `0.0.0.0`（仅当 dycast 与 blivechat 不同机时需要）。
- 无弹幕：确认 dycast 已连接房间且转发状态为已连接；查看 `log/douyin-relay.log`。
- SDK 版本不兼容：使用与当前 blivechat 匹配的源码运行插件。

## 端到端验证清单

1. `data/plugins/douyin-relay/plugin.json` 存在且 `run` 指向本机可用的 `python`。
2. 启动 blivechat，插件列表中出现「抖音弹幕中继」，启用后状态为已连接（子进程已启动）。
3. 日志中出现 `Douyin relay WebSocket listening ws://...`。
4. dycast 填写相同 WebSocket URL 并点击转发，日志出现 `dycast forwarder connected`。
5. 抖音侧发送聊天弹幕，OBS/浏览器源中可见 `[抖音]` 前缀内容。
6. 停止 dycast 转发后再开启，插件无崩溃，弹幕恢复。
