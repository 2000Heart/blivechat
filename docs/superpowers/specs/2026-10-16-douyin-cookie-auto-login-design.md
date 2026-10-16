# douyin-relay：可控浏览器自动登录与 Cookie 静默续期

日期：2026-10-16  
状态：评审修订（待实现）  
范围：`plugins/douyin-relay`

## 背景与目标

sidecar 连接抖音直播依赖 `douyin_cookie`（完整 Cookie，含 HttpOnly）。当前需用户手动从小书签或 DevTools 复制粘贴，体验差且易漏 HttpOnly。

**目标**

1. 管理页提供「登录抖音」：用可控浏览器（有头）打开直播站，登录后自动写入完整 Cookie。
2. 登录未过期时，插件启动后**静默续期**并写回配置，用户不必每次打开管理页更新。
3. 保留手动粘贴与小书签作为兜底。

**非目标（本版）**

- 不申请 / 不复用抖音开放平台 OAuth（直播站 Cookie 无对等设备授权流）。
- 不读取系统日常 Chrome 用户配置目录。
- 不把管理后台改成 Web（HTTP API 预留，便于日后迁移）。
- 不做「连房运行中 Cookie 突然失效后自动弹窗重登」的完整闭环（仅日志 + status；后续可加）。

## 为何不走「OAuth 回调」

调研 `workbuddy2api-panel` 一类项目：其「跳转登录后自动拿凭证」依赖平台**官方 CLI 设备授权**（`auth/state` → 用户打开 `authUrl` → 客户端轮询 `auth/token`），并非本机 `redirect_uri` 劫持，也不是页面脚本读 Cookie。

`live.douyin.com` 没有对第三方暴露的同类设备流，因此本设计采用 **Playwright 控制的系统浏览器 + Cookie 罐读取**。

## 方案选择

在「可控浏览器」方向下比较：

| 方案 | 结论 |
|------|------|
| A. dycast sidecar 内用已有 `playwright-core` + 系统 Chrome | **采用** |
| B. Python 再引 Playwright | 与 sidecar 重复，打包更重 |
| C. PySide6 QWebEngine 内嵌 | 依赖重，且不利于日后 Web 管理 |

sidecar 已存在 `playwright-core` 与 `resolveBrowserExecutablePath()` / `CHROME_PATH`（见 `dycast/src/sidecar/engine.ts`），弹幕连接使用 **headless** 实例；登录/续期使用**另一套** Browser 实例，互不共用。

## 架构

```text
管理 UI (macOS: Tk；其它: PySide6)
        ←→ 插件 Python（写 config.ini）
        ←→ dycast sidecar login API
              Playwright persistent context
              持久 profile
              browserContext.cookies()
```

**两条路径共用同一持久 profile**。路径相对插件根 `config.BASE_PATH`（即 `plugins/douyin-relay/`），默认 `data/douyin-browser-profile`，解析后绝对路径为 `plugins/douyin-relay/data/douyin-browser-profile/`。gitignore 与该默认路径一致。

| 路径 | 触发 | 浏览器 | 成功 | 失败 |
|------|------|--------|------|------|
| 静默续期 | sidecar 就绪后、**连房之前**（可配置关闭） | headless | 写回 `douyin_cookie`，再 disconnect + connect | `need_login`，不自动弹窗；用磁盘上已有 cookie 连房 |
| 交互登录 | 管理页「登录抖音」 | headed | Python 写回 cookie 后 disconnect + connect | 用户取消 → `cancelled`；超时 → `need_login` |

首次或过期时：**不**在无人值守下自动弹出有头窗口；仅提示用户到管理页点击登录。

`relay_backend` 不是 `sidecar` 时，静默续期与登录 API 均为 no-op（没有该 Node 进程）。

## Sidecar API

均挂在现有 `__api/dycast/` 下。Vite 当前 `host` 可能是 `0.0.0.0`，因此新路由必须拒绝非回环 `remoteAddress`（`127.0.0.1` / `::1`），不能只依赖配置声明。

### Profile 锁

进入 `running` 必须**同步占坑**（在 `await launch` 之前），再启动浏览器。任何离开 `running` 的路径（`done` / `need_login` / `error` / `cancelled`）都要先 `close()` persistent context，确认 Chromium 对 `userDataDir` 的锁已释放，再改 phase。`phase=running` 时第二次 `start` 返回 `409`，不得再开第二个 Chromium。

### `POST /__api/dycast/login/start`

占坑成功后**立刻**返回 `202`，body 只有 `phase` / `mode` / `message`，不含 Cookie。登录在后台进行；调用方轮询 status。禁止把 HTTP 响应拖到登录结束（Python bridge 超时约 3 秒）。

Body：

```json
{
  "mode": "interactive" | "silent"
}
```

`profileDir` 与超时**不接受请求体覆盖**。sidecar 使用插件启动时写入的配置（或环境变量），目录必须是配置解析出的那一个绝对路径。

- `interactive`：有头打开 `https://live.douyin.com/`，超时用 `cookie_login_timeout_seconds`（默认 300）。
- `silent`：无头加载同一 profile，超时用 `cookie_silent_timeout_seconds`（默认 30），避免拖住插件 `init()`。

### `GET /__api/dycast/login/status`

给管理页 / 通用 status 的字段：

```json
{
  "phase": "idle|running|done|need_login|error|cancelled",
  "mode": "interactive|silent|null",
  "cookieLength": 0,
  "message": "",
  "updatedAt": 0
}
```

Python 写配置需要 Cookie 时，使用一次性字段：仅 `phase=done` 且尚未被消费时，同一次 status 可带 `cookie`（`name=value; ...`）。Python 成功写入后必须再调一次消费接口，或在下一次 status 中 `cookie` 已清空。错误响应与日志禁止包含 Cookie 正文，只记录 `cookieLength`。

管理页展示的 status **不得**包含 `cookie` 字符串。

### `POST /__api/dycast/login/cancel`

先关闭登录浏览器并释放 profile 锁，再把 `phase` 设为 `cancelled`。

## 登录 / 仍有效判定

必须使用 Playwright `browserContext.cookies()`，按 domain 过滤 `.douyin.com` / `live.douyin.com` 后再序列化。禁止用 `document.cookie`（拿不到 HttpOnly）。

纯函数判定（单测不启浏览器）：

1. 存在会话类 Cookie（可维护白名单，例如名匹配 `sessionid`、`sessionid_ss`、`sid_tt`、`uid_tt`、`uid_tt_ss` 等）；
2. 导出的 Cookie 串（`name=value; ...`）长度 **≥ 200**（常量；过短视为未登录）；
3. 静默模式额外：若导航 URL 主机/路径明显属于登录或通行证（例如含 `login`、`passport`、`sso`），或关键会话 Cookie 缺失 → `need_login`。

交互模式：两次判定间隔 **至少 1 秒**，且都满足 (1)(2) 后再置 `done`。

phase 互斥：

- 用户点取消 → `cancelled`
- 超时 → `need_login`，`message` 写明超时
- 找不到浏览器 → `error`，`message` 含设置 `CHROME_PATH` 的提示

浏览器可执行文件查找顺序：`CHROME_PATH` → Playwright `channel: 'chrome'`，再 `msedge` → 各平台常见路径（macOS `/Applications/...`；Windows `%LOCALAPPDATA%` 与 `Program Files` 下的 Chrome/Edge；Linux `google-chrome` / `chromium` / `chromium-browser`）。

## 插件 Python 行为

启动顺序（`cookie_auto_refresh=true` 且 `relay_backend=sidecar`）写死，禁止先连房再后台续期：

1. sidecar 就绪。
2. 发起 `silent`（`POST` 立即返回），轮询 status，最长等待 `cookie_silent_timeout_seconds`。
3. `done`：仅由 Python 把 `douyin_cookie` 写入 `config.ini`（临时文件 + `os.replace`，保留 `interpolation=None`，只改该键），然后 **disconnect + connect**，使新 Cookie 进入 `__dy_cookie`。
4. `need_login` / `error` / 静默超时：打日志，status 透出；若磁盘上已有 `douyin_cookie`，用旧值 connect。不阻断 B 站主链路，不自动弹出有头窗口。
5. `cookie_auto_refresh=false`：跳过 silent，按现有逻辑用磁盘 cookie connect。

管理 action：`login_start`、`login_cancel`。给管理页的 status 只含 `phase` / `mode` / `cookieLength` / `message`，不含 Cookie 正文。

交互登录 `done` 后同样只由 Python 写配置并 disconnect + connect。管理页只刷新输入框显示（可用长度或占位，不在 `done` 时再走一遍「保存配置」以免双写整个 `[relay]`）。用户点「保存配置」仍走现有手动保存，后写生效。

## 配置项

`[relay]` 新增（均有默认）：

| 键 | 默认 | 含义 |
|----|------|------|
| `cookie_auto_refresh` | `true` | 启动后是否静默续期 |
| `douyin_browser_profile_dir` | `data/douyin-browser-profile` | 相对插件根 `config.BASE_PATH` |
| `cookie_login_timeout_seconds` | `300` | 交互登录超时秒数 |
| `cookie_silent_timeout_seconds` | `30` | 静默续期超时秒数 |

既有 `douyin_cookie` 语义不变。

## 管理 UI

macOS 实际走 Tk（`admin_ui.py` 在 darwin 上不走 PySide6）。Tk 与 PySide6 **同一套** action 与文案。

- 按钮：「登录抖音」「取消登录」（仅 `phase=running` 且 mode 为 interactive 时启用取消）。
- 状态文案：idle / 静默续期中 / 等待浏览器登录 / 已更新（只显示长度）/ 需要重新登录 / 已取消 / 错误信息。
- `done` 后刷新输入框，不在 UI 侧再保存整份配置。
- 保留：打开抖音直播、如何获取 Cookie、复制小书签、手动输入框。

## 文件改动清单

| 路径 | 说明 |
|------|------|
| `dycast/src/sidecar/cookie-login.ts`（新） | 登录会话状态机、判定、导出 Cookie |
| `dycast/vite.douyin-proxy-cookie.ts` | 注册 login 路由 |
| `dycast/src/sidecar/engine.ts` | 抽出浏览器路径解析（`CHROME_PATH` → channel → Win/mac/Linux 路径）；与 login 实例隔离 |
| `main.py` 及 runtime 相关 | 先静默续期再连房、写配置、status |
| `admin_ui.py` | Tk 与 PySide6 均提供登录/取消与不含 Cookie 正文的状态 |
| `config.py`、`data/config.example.ini` | 新配置键 |
| `README.md` | 用户文档：首次登录 + 之后静默 |
| `.gitignore` 或插件级忽略 | `douyin-browser-profile/` |
| `tests/` | 判定、序列化、状态机（CI 不启真浏览器） |

## 安全

- Cookie 与 profile 等同账号凭证：勿提交仓库；profile 目录权限随本机用户。
- 新 login 路由拒绝非回环来源；`profileDir` 不可由请求体任意指定。
- 管理页 status、错误响应、日志只出现 `cookieLength`，不出现 Cookie 正文。

## 测试计划

**单测（无浏览器）**

- 会话 Cookie 白名单命中/未命中；登录 URL 判定；Cookie 序列化格式。
- 状态机可注入假浏览器（不 import Playwright）：占坑后重复 start 冲突；离开 `running` 前必须先 close；用户取消为 `cancelled`，超时为 `need_login`。

**手工冒烟**

1. 空配置：静默 → need_login；交互登录成功 → 可连房。
2. 重启插件不打开管理页：静默成功并连房。
3. 删除 profile 或人为过期：静默 need_login，再登录可恢复。
4. 取消与超时行为符合预期。
5. 手动粘贴与自动抓取互相覆盖正确。

## 风险

- 抖音变更 Cookie 名或登录跳转 → 需更新白名单与 URL 规则。
- 自动化浏览器可能触发风控 → 优先系统 Chrome + 持久 profile；失败回落手动粘贴。
- 浏览器路径按「查找顺序」实现；找不到时 login `message` 提示 `CHROME_PATH`，并回落手动粘贴或磁盘上旧 cookie。

## 实现顺序建议

1. sidecar：`cookie-login` 模块 + API + 浏览器路径增强。  
2. Python：静默触发、写配置、status。  
3. 管理 UI 按钮与文案。  
4. 配置项、gitignore、README。  
5. 单测 + 手工冒烟清单验收。
