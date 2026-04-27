# 抖音弹幕中继（douyin-relay）

将内置在插件目录下的 [dycast](https://github.com/skmcj/dycast) 通过 WebSocket 转发的弹幕注入到 blivechat，与 B 站弹幕同屏显示（前端模板如 `liquid-glass` 无需修改）。

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
2. 按需修改 `[relay]` 配置：
   - `mode=relay`：监听 dycast 的 WebSocket 转发。
   - relay 模式下使用 `listen_host`、`listen_port`、`ws_path`。
   - sidecar 自动连接可选 `douyin_room_id` 与 `douyin_cookie`。
3. relay 默认监听：`ws://127.0.0.1:18765/`（路径为 `/` 时，dycast 填写 `ws://127.0.0.1:18765` 或 `ws://127.0.0.1:18765/` 均可）。

## 使用步骤

1. 启动 blivechat，在插件管理中启用 **抖音弹幕中继**（首次需在 `data/plugins/douyin-relay/plugin.json` 中把 `enabled` 改为 `true`，或通过管理界面开启）。
2. relay 模式：
   - 在插件列表中点击本插件的 **管理**，在弹出窗口中复制 **WebSocket 地址**（与 `data/config.ini` 中 `[relay]` 的监听配置一致）。
   - 确认日志出现：`抖音中继已启动，请在 dycast 填写 ws://...`。
   - 使用插件目录下的 `dycast/`（sidecar 默认从这里启动）连接房间后，在 **WS地址** 填入该 URL 并点击 **转发**。
3. 打开 blivechat 房间页与 OBS 浏览器源，应能看到带 `[抖音]` 前缀的弹幕。

## 数据格式说明

与 dycast 行为一致：

- 转发连接建立后，会先推送一条 **直播间信息 JSON 对象**（仅记录日志，不注入）。
- 之后每条为 **弹幕消息数组** 的 JSON 序列化结果。

## 数据契约

插件内部新增统一事件契约 `UnifiedEvent`（见 `contract.py`），用于冻结字段与空值语义，再转换为现有 injector 消费结构。

- 必填字段：
  - `event_id`：事件唯一 ID。优先使用上游消息 `id`，缺失时基于 `uid + ts + text (+ room)` 生成稳定回退值，降低同文案消息碰撞概率。
  - `platform`：`bilibili` 或 `douyin`。
  - `event_type`：事件类型（当前已接入 `chat.message`、`like.action`、`member.join`、`social.follow`、`gift.send`）。
  - `ts`：毫秒时间戳。
  - `actor`：事件发起人，包含 `id`、`name`、`avatar_url`。
  - `platform_meta`：平台特定扩展信息，必须按平台区分。
- 可选字段（允许为空）：
  - `content`：内容结构（聊天消息包含 `text`）。
  - `monetization`：商业化信息（如礼物相关字段），聊天消息为 `None`；`gift.send` 事件包含 `gift_name`、`gift_count`、`gift_id`、`gift_icon_url`。
  - `fan_identity`：粉丝身份信息，当前聊天消息为 `None`。
- 空值语义：
  - `None` 表示“上游未提供或当前事件不适用”，不是空字符串占位。
  - 空字符串只用于“字段本身是字符串且上游给出空值”的场景。

### platform_meta 约束

- `douyin`：
  - 结构：`{ platform: "douyin", room_id, room_num, membership_type, membership_name, fans_badge_level, fans_badge_name }`
  - `membership_type` / `membership_name`：会员身份扩展字段，未提供时为 `None`。
  - `fans_badge_level` / `fans_badge_name`：粉丝牌扩展字段，未提供时为 `None`；不会伪造。
- `bilibili`：
  - 结构：`{ platform: "bilibili", medal_name, medal_level }`
  - 作为统一契约的保留分支，用于与 B 站来源对齐。

## 依赖

与主项目一致，需已安装 `aiohttp`、`cachetools`（见主仓库 `requirements.txt` / `blivedm/requirements.txt`）。

## 故障排查

- 无法连接：检查防火墙、`listen_host` 是否应用 `0.0.0.0`（仅当 dycast 与 blivechat 不同机时需要）。
- 无弹幕：确认 dycast 已连接房间且转发状态为已连接；查看 `log/douyin-relay.log`。
- SDK 版本不兼容：使用与当前 blivechat 匹配的源码运行插件。

## 本地可执行验证命令

在 `blivechat` 仓库根目录执行：

```bash
# 1) Python 侧：插件关键文件语法/可运行性（编译）检查
python3 -m compileall -q plugins/douyin-relay
python3 -m py_compile plugins/douyin-relay/*.py

# 2) 前端侧：lint + 最小构建检查
cd frontend
npm run lint
npm run build
```

说明：
- `py_compile` 通过代表关键文件语法正确，可被解释器加载。
- `npm run build` 通过代表前端产物可正常打包；若仅出现体积类 warning，一般不阻断 relay 功能验收。

## 端到端验收清单

### relay 模式（最小验收）

1. 在 `plugins/douyin-relay/data/config.ini` 设置：
   - `[relay] mode=relay`
   - 按需配置 `listen_host`、`listen_port`、`ws_path`（默认 `ws://127.0.0.1:18765/`）。
2. 启动 blivechat 并启用插件，在管理页复制 WebSocket 地址。
3. dycast 连接抖音房间后，将该地址填入 dycast 的 WS 地址并点击转发。
4. 插件日志出现 `Douyin relay WebSocket listening ...` 与 `dycast forwarder connected`。
5. 抖音侧发送聊天消息，确认房间页/OBS 浏览器源出现 `[抖音]` 前缀弹幕。
6. 手动断开再重连 dycast 转发，确认插件不崩溃且消息恢复。

## 回归检查清单（B 站链路不退化）

1. 不启用本插件时，B 站弹幕展示与历史版本一致（基线冒烟）。
2. 启用本插件后，B 站弹幕仍持续到达、顺序正常、无明显延迟抖动。
3. 在 relay 模式下，B 站弹幕样式、过滤逻辑、OBS 输出不被破坏。
4. 反复启停本插件后，B 站房间连接与消息消费无异常中断。
5. 查看主程序与插件日志，确认无持续报错、无异常重启风暴。

## 回滚预案（sidecar 快速切回 legacy relay）

目标：当 sidecar 模式出现异常时，快速恢复到已验证的 legacy relay 链路。

1. 修改 `plugins/douyin-relay/data/config.ini`：
   - 保持 `mode=relay`，将 `relay_backend=sidecar` 改为 `relay_backend=legacy`。
   - 恢复/确认 `listen_host`、`listen_port`、`ws_path` 为可用值（建议默认 `127.0.0.1:18765`、`/`）。
2. 在插件管理中禁用再启用「抖音弹幕中继」，确保新配置生效。
3. 在 dycast 重新填入插件管理页展示的 WS 地址并启动转发。
4. 观察 `log/douyin-relay.log`，确认监听与连接日志出现且弹幕恢复。
5. 若仍异常，临时禁用本插件以保障 B 站主链路稳定，待问题定位后再恢复。

## 已知限制与风险提示

- relay 模式依赖 dycast 可用性；dycast 未连接房间或未开启转发时不会有抖音消息输入。
- 前端构建存在体积与目标环境 `async/await` warning，当前不阻断构建，但建议后续专项治理兼容性与包体积。
- 插件与主进程通过子进程通信，若运行环境权限/防火墙限制端口监听，可能导致 relay 建链失败。
