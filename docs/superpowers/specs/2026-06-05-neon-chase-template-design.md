# 赛博追光（Neon Chase）弹幕模板设计

## 概述

为 blivechat 设计的新自定义 HTML 弹幕模板，赛博霓虹风格，主要特色为：
- 用户信息独立一行，气泡仅包裹聊天内容
- 大航海用户（舰长/提督/总督）气泡使用顺时针追光边框
- 付费消息（礼物/SC）使用线条呼吸灯边框
- 深色主题，霓虹色码系统区分身份等级

## 效果映射

| 类型 | 边框效果 | 颜色 |
|------|---------|------|
| 普通用户 | 静态暗灰边框（#444，opacity 0.06） | 灰 |
| 舰长 | 追光 3s 顺时针 | 蓝(#2196F3) → 青(#00E5FF) |
| 提督 | 追光 3s 顺时针 | 紫(#9C27B0) → 品红(#E040FB) |
| 总督 | 双段追光 3s 顺时针（文字微发光） | 金(#FFD700) → 橙(#E65100) |
| 房管 | 静态绿边框 | 绿(#4CAF50) |
| 主播 | 静态品红边框 | 品红(#FF4081) |
| 礼物（免费） | 呼吸灯 2.5s | 淡蓝(#00E5FF) |
| 礼物（付费） | 呼吸灯 2.5s | 金(#FFD700) |
| 醒目留言（大额） | 呼吸灯 2.5s | 炽红(#FF1744) |

## 消息布局

每条消息的 HTML 结构：

```html
<div class="nc-message">                           <!-- 一条消息容器 -->
  <div class="nc-author-row">                       <!-- 用户信息行 -->
    <img-shadow avatarUrl></img-shadow>              <!-- 头像 24x24 -->
    <span class="nc-timestamp">14:32</span>          <!-- 时间 -->
    <author-chip                                     <!-- 用户名 + 徽章 -->
      authorName authorType privilegeType
      medalLevel medalName
    ></author-chip>
  </div>
  <div class="nc-bubble nc-chase">                  <!-- 气泡（追光或呼吸灯） -->
    <div class="nc-bubble-inner">                   <!-- 气泡内衬 -->
      <span>弹幕内容文本</span>
    </div>
  </div>
</div>
```

- 用户信息行与气泡之间间距 6px
- 气泡使用 `display: inline-block`，宽度自适应内容
- 气泡圆角 12px

## 追光边框实现

使用 CSS `@property --angle` + `conic-gradient` 伪元素实现，纯 CSS 无需 JS：

```css
@keyframes chase {
  0% { --angle: 0deg; }
  100% { --angle: 360deg; }
}

@property --angle {
  syntax: '<angle>';
  initial-value: 0deg;
  inherits: false;
}

.nc-chase {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  display: inline-block;
}

.nc-chase::before {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: 14px;
  z-index: 0;
  background: conic-gradient(
    from var(--angle, 0deg),
    var(--nc-dim) 0deg,
    var(--nc-dim) 270deg,
    var(--nc-c1) 285deg,
    var(--nc-c2) 315deg,
    var(--nc-c1) 340deg,
    var(--nc-dim) 355deg,
    var(--nc-dim) 360deg
  );
  animation: chase 3s linear infinite;
}

.nc-chase .nc-bubble-inner {
  position: relative;
  margin: 2px;
  border-radius: 11px;
  z-index: 1;
}
```

追光长尾约 85 度（从 dim 到 c1/c2 再回到 dim），\~3 秒一圈顺时针旋转。

### 身份 → CSS 变量映射

```css
/* 舰长 */
.nc-chase { --nc-dim: rgba(33,150,243,0.06); --nc-c1: #2196F3; --nc-c2: #00E5FF; }
/* 提督 */
.nc-chase { --nc-dim: rgba(156,39,176,0.06); --nc-c1: #9C27B0; --nc-c2: #E040FB; }
/* 总督（双段追光） */
.nc-chase-dual { --nc-dim: rgba(255,215,0,0.06); --nc-c1: #FFD700; --nc-c2: #E65100; }
```

### 总督双段追光

总督使用双段追光（与舰长/提督的单段追光区分），在边框上同时有两个金色亮段顺时针旋转：

```css
@keyframes chase-dual {
  0% { --angle: 0deg; }
  100% { --angle: 360deg; }
}

.nc-chase-dual {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  display: inline-block;
}

.nc-chase-dual::before {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: 14px;
  z-index: 0;
  background: conic-gradient(
    from var(--angle, 0deg),
    var(--nc-dim) 0deg,
    var(--nc-dim) 120deg,
    var(--nc-c1) 130deg,
    var(--nc-c2) 150deg,
    var(--nc-dim) 165deg,
    var(--nc-dim) 290deg,
    var(--nc-c1) 300deg,
    var(--nc-c2) 320deg,
    var(--nc-dim) 335deg,
    var(--nc-dim) 360deg
  );
  animation: chase-dual 3s linear infinite;
}

.nc-chase-dual .nc-bubble-inner {
  position: relative;
  margin: 2px;
  border-radius: 11px;
  z-index: 1;
}
```

## 呼吸灯边框实现

仅边框颜色在 dim/bright 之间缓慢变化，文字不受影响：

```css
@keyframes lineBreathe {
  0%, 100% { border-color: var(--nc-dim); }
  50% { border-color: var(--nc-bright); }
}

.nc-breathe {
  border-radius: 12px;
  display: inline-block;
  border: 2px solid var(--nc-dim);
  animation: lineBreathe 2.5s ease-in-out infinite;
}
```

## 模板文件结构

```
data/custom_public/templates/neon-chase/
  template.json              # 模板元信息
  index.html                 # 入口 HTML
  css/
    main.css                 # 全局样式
    custom.css               # 用户自定义样式入口
    neon-chase/
      nc-html.css            # HTML 基础样式重置
      nc-icon.css            # 图标样式
      nc-img-shadow.css      # 头像阴影组件
      nc-live-chat-renderer.css           # 渲染器容器
      nc-live-chat-item-list-renderer.css # 消息列表
      nc-live-chat-text-message-renderer.css    # 文本消息
      nc-live-chat-paid-message-renderer.css    # 付费消息
      nc-live-chat-membership-item-renderer.css # 开通大航海
      nc-live-chat-author-badge-renderer.css    # 身份徽章
      nc-live-chat-author-chip.css              # 用户信息条
      nc-live-chat-ticker-renderer.css          # Ticker
  js/
    vendor/
      lodash.min.js
      vue.global.js           # Vue 3（沿用 liquid-glass 的方式）
      blcsdk.js               # 从 blivechat 项目复制
    ChatRenderer/
      constants.js            # 常量（复用 YouTube/liquid-glass 模式）
      ImgShadow.js            # 头像阴影组件
      AuthorBadge.js          # 身份徽章
      AuthorChip.js           # 用户信息条（头像 + 名称 + 徽章）
      TextMessage.js          # 文本消息组件
      PaidMessage.js          # 付费消息组件（礼物/SC）
      MembershipItem.js       # 开通大航海组件
      Ticker.js               # Ticker 组件（付费消息横幅）
      index.js                # ChatRenderer 主组件
    main.js                   # Vue app 入口
  img/
    guard-level-1.png         # 总督徽章
    guard-level-2.png         # 提督徽章
    guard-level-3.png         # 舰长徽章
```

## Vue 组件渲染结构

```
<App (Vue 3)>
  └── <ChatRenderer>                    (nc-live-chat-renderer)
        ├── <Ticker>                    (付费消息横幅)
        └── <nc-live-chat-item-list-renderer>
              └── #items
                    ├── <div.nc-message>          每条消息
                    │     ├── <div.nc-author-row>
                    │     │     ├── <ImgShadow>        头像
                    │     │     ├── <span.nc-ts>      时间
                    │     │     └── <AuthorChip>       用户名 + 徽章
                    │     └── <nc-bubble>              气泡（边框动效）
                    │           └── <span>             聊天内容
                    ├── <div.nc-message> 重复
                    ...
```

## ChatRenderer 模板详情

ChatRenderer 的 Vue 模板（核心结构）：

```html
<nc-live-chat-renderer>
  <ticker :messages="paidMessages"></ticker>
  <nc-live-chat-item-list-renderer allow-scroll>
    <div ref="scroller" id="item-scroller" class="animated">
      <div ref="itemOffset" id="item-offset">
        <div ref="items" id="items">
          <template v-for="message in messages">
            <text-message v-if="message.type === MESSAGE_TYPE_TEXT"
              :time="message.time" :avatarUrl="message.avatarUrl"
              :authorName="message.authorName" :authorType="message.authorType"
              :privilegeType="message.privilegeType"
              :contentParts="getShowContentParts(message)"
              :medalLevel="message.medalLevel" :medalName="message.medalName"
            ></text-message>
            <!-- 礼物 / SC / 开通大航海 类似 -->
          </template>
        </div>
      </div>
    </div>
  </nc-live-chat-item-list-renderer>
</nc-live-chat-renderer>
```

## 组件属性传递

TextMessage 组件接收以下 props，并在渲染时分别用于用户信息行和气泡：

| Prop | 用途 |
|------|------|
| avatarUrl | 用户信息行 → ImgShadow |
| time | 用户信息行 → 时间戳 |
| authorName | 用户信息行 → AuthorChip |
| authorType | 用户信息行 → AuthorChip（身份样式） |
| privilegeType | 用户信息行 → AuthorChip + 气泡边框效果选择 |
| contentParts | 气泡 → 文本/表情渲染 |
| medalLevel | 用户信息行 → AuthorChip（粉丝牌等级） |
| medalName | 用户信息行 → AuthorChip（粉丝牌名称） |

边框效果选择逻辑（在模板中通过 privilegeType 和 message type 判断）：

```
user type  →  privilegeType=0 → 普通
              privilegeType=3 → 追光（舰长）
              privilegeType=2 → 追光（提督）
              privilegeType=1 → 双段追光（总督）
              isAdmin → 静态绿边框（房管）
              isOwner → 静态品红边框（主播）

paid type  →  price <= 0 → 淡蓝呼吸（免费礼物）
              price < 100 → 金色呼吸（付费礼物）
              price >= 100 → 炽红呼吸（大额SC）
```

## main.js 逻辑

```javascript
const app = createApp({
  components: { ChatRenderer },
  data() { return {
    config: { maxNumber: 60, showGiftName: false, mergeGift: true }
  }},
  async mounted() {
    blcsdk.setMsgHandler(this)
    await blcsdk.init()
    let cfg = blcsdk.getConfig()
    this.config.maxNumber = cfg.maxNumber
    this.config.showGiftName = cfg.showGiftName
    this.config.mergeGift = cfg.mergeGift
  },
  methods: {
    addMsg(msg) { this.$refs.renderer.handleMessageGroup([msg]) },
    delMsgs(ids) { /* ... */ },
    updateMsg(id, newValuesObj) { /* ... */ },
  }
})
app.config.compilerOptions.isCustomElement = (tag) => tag.startsWith('nc-')
app.mount('#app')
```

## 模板配置

```json
{
  "name": "赛博追光",
  "version": "1.0.0",
  "author": "blivechat",
  "description": "赛博霓虹风格弹幕模板，追光边框用于大航海，呼吸灯边框用于付费消息",
  "thumbnail": "",
  "url": "index.html"
}
```
