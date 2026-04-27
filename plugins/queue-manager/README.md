# 排队管理器（queue-manager）

用于 blivechat 的弹幕排队插件：用户发送 `排队` 进入队列，队内用户送礼后按累计礼物价值自动重排，可在插件管理页执行 `过号` 和 `移除`，并提供 OBS 浏览器源页面。

## 安装

blivechat 运行时只扫描 `data/plugins/<plugin-id>/plugin.json`。

请将本目录复制或软链到：

`<blivechat 根目录>/data/plugins/queue-manager/`

开发模式可在 `data/plugins` 下软链：

`queue-manager -> ../../plugins/queue-manager`

## 配置

首次启动会在 `data/config.json` 生成默认配置：

- `requireFansMedal`: 是否必须有粉丝团
- `minFansLevel`: 最低粉丝团等级
- `requireGuard`: 是否必须有舰队
- `minGuardLevel`: 最低舰队等级（舰长=1）
- `maxQueueSize`: 最大队列长度

## 使用

1. 在 blivechat 插件页启用「排队管理器」。
2. 点击「管理」自动打开后台页。
3. 复制后台中的 `OBS 链接` 到 OBS 浏览器源。

## 行为规则（V1）

- 关键词固定为 `排队`
- 重复报名忽略（保留原顺序）
- 不满足资格静默忽略
- 队内用户送礼后按累计礼物值降序重排
- 同礼物值按报名时间先后排序
- 每个直播间（roomKey）独立队列

## 端到端验证清单

1. 用户 A 发送 `排队`，成功入队。
2. 用户 A 再次发送 `排队`，顺序不变。
3. 不满足门槛用户发送 `排队`，不入队且无提示。
4. 队内用户送礼后，按累计礼物值重排。
5. 后台点击 `过号`，队首出队，OBS 实时更新。
6. 后台输入 `userKey` 点击 `移除`，目标用户出队，OBS 实时更新。
7. 新开一个直播间房间，队列互不影响。
