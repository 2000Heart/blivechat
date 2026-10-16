# douyin-relay：可控浏览器自动登录与 Cookie 静默续期

日期：2026-10-16  
状态：已定稿（待实现）  
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
管理 UI (PySide6)          插件 Python                 dycast sidecar
  登录/取消/状态    ←→    action + 写 config.ini  ←→   login API
                                                      Playwright
                                                      持久 profile
                                                      Cookie 罐
```

**两条路径共用同一持久 profile**（默认 `plugins/douyin-relay/data/douyin-browser-profile/`）：

| 路径 | 触发 | 浏览器 | 成功 | 失败 |
|------|------|--------|------|------|
| 静默续期 | sidecar 就绪后自动（可配置关闭） | headless | 写回 `douyin_cookie` | `need_login`，不自动弹窗 |
| 交互登录 | 管理页「登录抖音」 | headed | 写回并可选自动重连 | 取消 / 超时 → `need_login` |

首次或过期时：**不**在无人值守下自动弹出有头窗口；仅提示用户到管理页点击登录。

## Sidecar API

均挂在现有 `__api/dycast/` 下，仅本机回环访问。

### `POST /__api/dycast/login/start`

Body：

```json
{
  "mode": "interactive" | "silent",
  "profileDir": "/abs/or/rel/path",
  "timeoutSeconds": 300
}
```

- `profileDir` / `timeoutSeconds` 由插件 Python 按 `config.ini` 解析后传入（绝对路径优先）；缺省时 sidecar 使用内置默认（与配置默认值一致）。
- 若已有会话 `phase=running`：返回冲突错误（同时只允许一个登录会话）。
- `interactive`：有头打开 `https://live.douyin.com/`，开始等待登录判定。
- `silent`：无头加载同一 profile，尝试判定仍登录并导出 Cookie。

### `GET /__api/dycast/login/status`

```json
{
  "phase": "idle|running|done|need_login|error|cancelled",
  "mode": "interactive|silent|null",
  "cookie": "",
  "cookieLength": 0,
  "message": "",
  "updatedAt": 0
}
```

`cookie` 仅在 `phase=done` 时返回非空字符串（`name=value; ...`，与现有粘贴解析兼容）。

### `POST /__api/dycast/login/cancel`

关闭当前登录用浏览器，`phase` → `cancelled`。

## 登录 / 仍有效判定

以 Cookie 罐为主（不依赖脆弱 DOM 文案）：

1. 存在会话类 Cookie（可维护白名单，例如名匹配 `sessionid`、`sessionid_ss`、`sid_tt`、`uid_tt`、`uid_tt_ss` 等）；
2. 导出的 Cookie 串（`name=value; ...`）长度 **≥ 200**（常量，单测可覆盖；过短视为未登录）；
3. 静默模式额外：若导航 URL 主机/路径明显属于登录或通行证（例如含 `login`、`passport`、`sso`），或关键会话 Cookie 缺失 → `need_login`。

交互模式：连续两次 poll 均满足 (1)(2) 后再置 `done`，降低半登录态误判。  
交互超时默认 300 秒，超时等同 cancel + `need_login`。

实现时将判定与序列化做成纯函数，便于单测。

## 插件 Python 行为

1. sidecar 启动成功且 `cookie_auto_refresh=true` 时发起一次 `silent`。
2. `done`：更新内存中的 cookie、原子写回 `config.ini` 的 `douyin_cookie`；若已配置房间号且策略需要，可触发/保持 sidecar connect（与现有「保存配置后重连」行为对齐）。
3. `need_login` / `error`：打日志，status 透出；不阻断 B 站主链路。
4. 管理 action：`login_start`、`login_cancel`；既有 status provider 增加 login 字段。
5. 用户手动保存 Cookie 仍覆盖同一字段（后写生效）。

## 配置项

`[relay]` 新增（均有默认）：

| 键 | 默认 | 含义 |
|----|------|------|
| `cookie_auto_refresh` | `true` | 启动后是否静默续期 |
| `douyin_browser_profile_dir` | `data/douyin-browser-profile` | 相对插件数据目录的持久 profile |
| `cookie_login_timeout_seconds` | `300` | 交互登录超时秒数 |

既有 `douyin_cookie` 语义不变。

## 管理 UI

- 按钮：「登录抖音」「取消登录」（仅 running 时启用）。
- 状态文案：idle / 静默续期中 / 等待浏览器登录 / 已更新 / 需要重新登录 / 错误信息。
- `done` 后填入 Cookie 输入框并自动保存配置；默认「保存后自动重连 sidecar」为开。
- 保留：打开抖音直播、如何获取 Cookie、复制小书签、手动输入框。

## 文件改动清单

| 路径 | 说明 |
|------|------|
| `dycast/src/sidecar/cookie-login.ts`（新） | 登录会话状态机、判定、导出 Cookie |
| `dycast/vite.douyin-proxy-cookie.ts` | 注册 login 路由 |
| `dycast/src/sidecar/engine.ts` | 抽出并增强浏览器路径解析（含 Windows 常见路径）；与 login 实例隔离 |
| `main.py` 及 runtime 相关 | 静默触发、写配置、status |
| `admin_ui.py` | 登录/取消与状态展示 |
| `config.py`、`data/config.example.ini` | 新配置键 |
| `README.md` | 用户文档：首次登录 + 之后静默 |
| `.gitignore` 或插件级忽略 | `douyin-browser-profile/` |
| `tests/` | 判定、序列化、状态机（CI 不启真浏览器） |

## 安全

- Cookie 与 profile 等同账号凭证：勿提交仓库；profile 目录权限随本机用户。
- login API 仅随 sidecar 绑在 `127.0.0.1`。
- 响应与日志避免完整打印 Cookie 内容（可用 length / 脱敏）。

## 测试计划

**单测（无浏览器）**

- 会话 Cookie 白名单命中/未命中；登录 URL 判定；Cookie 序列化格式。
- 状态机：idle → running → done | need_login | cancelled | error；重复 start 冲突。

**手工冒烟**

1. 空配置：静默 → need_login；交互登录成功 → 可连房。
2. 重启插件不打开管理页：静默成功并连房。
3. 删除 profile 或人为过期：静默 need_login，再登录可恢复。
4. 取消与超时行为符合预期。
5. 手动粘贴与自动抓取互相覆盖正确。

## 风险

- 抖音变更 Cookie 名或登录跳转 → 需更新白名单与 URL 规则。
- 自动化浏览器可能触发风控 → 优先系统 Chrome + 持久 profile；失败回落手动粘贴。
- Windows/Linux 浏览器路径需在 `resolveBrowserExecutablePath` 中补全（当前代码偏 macOS）。

## 实现顺序建议

1. sidecar：`cookie-login` 模块 + API + 浏览器路径增强。  
2. Python：静默触发、写配置、status。  
3. 管理 UI 按钮与文案。  
4. 配置项、gitignore、README。  
5. 单测 + 手工冒烟清单验收。
