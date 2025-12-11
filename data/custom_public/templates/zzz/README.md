# 绝区零风格弹幕模板

这是一个基于绝区零游戏设计风格的弹幕聊天界面模板。

## 安装说明

1. 确保所有文件都在 `data/custom_public/templates/zzz/` 目录下
2. 从 YouTube 模板复制必要的 vendor 文件：
   - 复制 `data/custom_public/templates/youtube/js/vendor/` 下的所有文件到 `js/vendor/`
3. 从 YouTube 模板复制并修改 JS 组件文件：
   - 复制 `data/custom_public/templates/youtube/js/ChatRenderer/` 下的文件
   - 将所有 `yt-` 开头的组件名改为 `zzz-`
   - 将所有 `yt-live-chat-` 改为 `zzz-live-chat-`
   - 将所有 `yt-img-shadow` 改为 `zzz-img-shadow`
   - 将所有 `yt-icon` 改为 `zzz-icon`

## 设计特点

- 深色主题（#000, #121212）
- 蓝色强调色（#007aff）
- 科技感边框和发光效果
- 圆角设计
- 渐变背景

## 文件结构

```
zzz/
├── template.json          # 模板配置
├── index.html            # 主 HTML 文件
├── css/                  # 样式文件
│   ├── main.css
│   ├── zzz-live-chat-renderer.css
│   ├── zzz-live-chat-text-message-renderer.css
│   ├── zzz-live-chat-author-chip.css
│   ├── zzz-live-chat-author-badge-renderer.css
│   ├── zzz-live-chat-paid-message-renderer.css
│   ├── zzz-live-chat-membership-item-renderer.css
│   └── zzz-live-chat-ticker-renderer.css
└── js/
    ├── main.js
    ├── vendor/           # 需要从 YouTube 模板复制
    └── ChatRenderer/     # 需要从 YouTube 模板复制并修改
```

## 注意事项

- 需要复制 YouTube 模板的 vendor 文件（lodash.min.js, vue.min.js, blcsdk.js）
- 需要复制并修改 YouTube 模板的 ChatRenderer 组件文件
- 所有组件名需要从 `yt-` 改为 `zzz-`

