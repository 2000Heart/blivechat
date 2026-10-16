# 抖音弹幕中继（douyin-relay）

把插件目录里的 [dycast](https://github.com/skmcj/dycast) 以 headless 进程拉起，将抖音弹幕注入 blivechat，与 B 站弹幕同屏显示（前端模板如 `liquid-glass` 无需修改）。

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

## 准备 headless

在 `dycast/` 安装依赖：

```bash
cd plugins/douyin-relay/dycast
npm install
```

插件用 `tsx` 和 `tsconfig.sidecar.json` 启动 headless，工作目录是 `dycast/`：

```text
node ./node_modules/tsx/dist/cli.mjs --tsconfig tsconfig.sidecar.json src/sidecar/headless.ts
```

`[relay]` 里的 `sidecar_node_exe` 可填 Node 绝对路径。留空或写成 `node` 时，先尝试 `dycast/.node` 下的便携 Node，再回退系统 `node`。

## 配置

1. 将 `data/config.example.ini` 复制为 `data/config.ini`（与示例同目录）。
2. 在 `[relay]` 中填写 `douyin_room_id`。Cookie 可先留空，登录成功后由管理页写入。
3. 管理页只监听回环地址。在插件列表点 **管理**，打开 `http://127.0.0.1:18771/admin`（端口以 `admin_port` 为准）。

### 如何填写 Cookie

在 blivechat 插件列表打开本插件 **管理**，浏览器进入 `http://127.0.0.1:18771/admin`：

- 首次没有有效 Cookie 时点 **登录抖音**，在弹出的浏览器窗口中完成登录。成功后 Cookie 写入配置；已填写房间号时会按新 Cookie 连接。
- 也可以把 Cookie 粘贴进管理页后保存。保存后以粘贴内容为准。
- `cookie_auto_refresh=true`（默认）时，插件启动后会用已保存的浏览器 profile 静默续期，不必先打开管理页。静默失败后再点 **登录抖音**。
- `cookie_auto_refresh=false` 只关闭启动时的静默续期。管理页登录和手动粘贴仍然可用。
- 提示找不到浏览器时，设置环境变量 **`CHROME_PATH`**，指向本机 Chrome / Chromium / Edge。

Cookie 等同账号登录态，请勿泄露或提交到公开仓库。

## 使用步骤

1. 在 `plugins/douyin-relay/dycast/` 执行 `npm install`。
2. 启动 blivechat，在插件管理中启用 **抖音弹幕中继**（首次需在 `data/plugins/douyin-relay/plugin.json` 中把 `enabled` 改为 `true`，或通过管理界面开启）。
3. 在插件列表点击 **管理**，打开 `http://127.0.0.1:18771/admin`，填写房间号并完成登录。
4. 打开 blivechat 房间页与 OBS 浏览器源，应能看到带 `[抖音]` 前缀的弹幕。

## 数据契约

插件内部使用统一事件契约 `UnifiedEvent`（见 `contract.py`），用于冻结字段与空值语义，再转换为 injector 消费结构。

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

```bash
python -m pip install -r plugins/douyin-relay/requirements.txt
```

管理页是本机网页，地址为 `http://127.0.0.1:18771/admin`。

## 故障排查

- 管理页打不开：确认插件进程已启动，浏览器地址为 `http://127.0.0.1:18771/admin`（端口与 `admin_port` 一致）。
- 无弹幕：确认房间号已保存、登录已完成，并查看 `log/douyin-relay.log`。
- headless 起不来：确认已在 `dycast/` 执行 `npm install`，且 Node 能加载 `tsx` 与 `tsconfig.sidecar.json`。
- SDK 版本不兼容：使用与当前 blivechat 匹配的源码运行插件。

## 本地可执行验证命令

在 `blivechat` 仓库根目录执行：

```bash
python3 -m compileall -q plugins/douyin-relay
python3 -m py_compile plugins/douyin-relay/*.py
```

在 `plugins/douyin-relay/dycast` 执行：

```bash
node --experimental-strip-types --test src/sidecar/live-probe.test.ts src/sidecar/headless-router.test.ts src/sidecar/cookie-login-session.test.ts src/sidecar/cookie-login-rules.test.ts src/sidecar/cookie-login-browser.test.ts
node ./node_modules/tsx/dist/cli.mjs --tsconfig tsconfig.sidecar.json src/sidecar/import-check.ts
```

## 验收清单

1. 在 `plugins/douyin-relay/dycast/` 执行 `npm install`。
2. 启动 blivechat 并启用插件。
3. 点击 **管理**，确认浏览器打开 `http://127.0.0.1:18771/admin`。
4. 在管理页登录并保存房间号后，房间页或 OBS 浏览器源出现 `[抖音]` 前缀弹幕。
5. 再次点击 **管理**，仍打开同一地址，插件进程保持运行。

## 回归检查清单（B 站链路不退化）

1. 不启用本插件时，B 站弹幕展示与历史版本一致。
2. 启用本插件后，B 站弹幕仍持续到达、顺序正常。
3. 反复启停本插件后，B 站房间连接与消息消费无异常中断。
4. 查看主程序与插件日志，确认无持续报错、无异常重启风暴。

## 已知限制与风险提示

- 抖音消息依赖 `dycast/` headless 与本机 Node。未安装依赖或房间未开播时不会有抖音消息。
- 管理页只接受回环地址。插件与主进程通过子进程通信，权限或防火墙限制本机回环时管理页无法打开。
