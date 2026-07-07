(function(root, factory) {
  root.chatRenderer = factory(
    root._,
    root.chatRendererConstants,
    root.chatRendererTextMessage.default,
    root.chatRendererPaidMessage.default,
    root.chatRendererMembershipItem.default,
  )
}(this,
function(_, constants, TextMessage, PaidMessage, MembershipItem) {
  const exports = {}

  const CHAT_SMOOTH_ANIMATION_TIME_MS = 84

  // ===== MessageItem 包装组件：将 v-if/v-else-if 条件渲染内聚到一个组件内 =====
  // 避免 Vue 3 编译器对 <template v-for> + v-if/v-else-if 产生 Block tree，
  // 导致 patch 时按位置匹配而非按 key 匹配，造成 splice 后所有列表项被重建。
  const MessageItem = {
    template: `
    <text-message v-if="msg.type === MESSAGE_TYPE_TEXT"
      :time="msg.time"
      :avatarUrl="msg.avatarUrl"
      :authorName="msg.authorName"
      :authorType="msg.authorType"
      :privilegeType="msg.privilegeType"
      :contentParts="getContentParts(msg)"
      :medalLevel="msg.medalLevel"
      :medalName="msg.medalName"
    ></text-message>
    <paid-message v-else-if="msg.type === MESSAGE_TYPE_GIFT"
      :time="msg.time"
      :avatarUrl="msg.avatarUrl"
      :authorName="getAuthorName(msg)"
      :authorType="msg.authorType"
      :privilegeType="msg.privilegeType"
      :price="msg.price"
      :priceText="''"
      :content="msg.price <= 0 ? '' : getGiftContent(msg)"
      :medalLevel="msg.medalLevel"
      :medalName="msg.medalName"
      :giftName="msg.giftName"
      :giftNum="msg.num"
    ></paid-message>
    <membership-item v-else-if="msg.type === MESSAGE_TYPE_MEMBER"
      :time="msg.time"
      :avatarUrl="msg.avatarUrl"
      :authorName="getAuthorName(msg)"
      :privilegeType="msg.privilegeType"
      :title="msg.title"
      :medalLevel="msg.medalLevel"
      :medalName="msg.medalName"
    ></membership-item>
    <paid-message v-else-if="msg.type === MESSAGE_TYPE_SUPER_CHAT"
      :time="msg.time"
      :avatarUrl="msg.avatarUrl"
      :authorName="getAuthorName(msg)"
      :authorType="msg.authorType"
      :privilegeType="msg.privilegeType"
      :price="msg.price"
      :content="getContent(msg)"
      :medalLevel="msg.medalLevel"
      :medalName="msg.medalName"
    ></paid-message>
    `,
    props: {
      message: Object,
      showGiftName: Boolean,
    },
    components: {
      TextMessage,
      PaidMessage,
      MembershipItem,
    },
    computed: {
      msg() { return this.message },
      MESSAGE_TYPE_TEXT() { return constants.MESSAGE_TYPE_TEXT },
      MESSAGE_TYPE_GIFT() { return constants.MESSAGE_TYPE_GIFT },
      MESSAGE_TYPE_MEMBER() { return constants.MESSAGE_TYPE_MEMBER },
      MESSAGE_TYPE_SUPER_CHAT() { return constants.MESSAGE_TYPE_SUPER_CHAT },
    },
    methods: {
      getContentParts(msg) { return constants.getShowContentParts(msg) },
      getAuthorName(msg) { return constants.getShowAuthorName(msg) },
      getContent(msg) { return constants.getShowContent(msg) },
      getGiftContent(msg) { return constants.getGiftShowContent(msg, this.showGiftName) },
    },
  }

  exports.default = {
    template: `
  <nc-live-chat-renderer style="--scrollbar-width:11px;">

    <nc-live-chat-item-list-renderer allow-scroll>
      <div ref="scroller" id="item-scroller" class="style-scope nc-live-chat-item-list-renderer animated">
        <div ref="itemOffset" id="item-offset" class="style-scope nc-live-chat-item-list-renderer">
          <div ref="items" id="items" class="style-scope nc-live-chat-item-list-renderer"
            :style="{ transform: \`translateY(\${Math.floor(scrollPixelsRemaining)}px)\` }"
          >
            <message-item
              v-for="message in messages"
              :key="message.id"
              :message="message"
              :showGiftName="showGiftName"
            ></message-item>
          </div>
        </div>
      </div>
    </nc-live-chat-item-list-renderer>
  </nc-live-chat-renderer>
    `,
    name: 'ChatRenderer',
    components: {
      MessageItem,
    },
    props: {
      maxNumber: Number,
      showGiftName: Boolean,
      mergeGift: Boolean,
    },
    data() {
      return {
        MESSAGE_TYPE_TEXT: constants.MESSAGE_TYPE_TEXT,
        MESSAGE_TYPE_GIFT: constants.MESSAGE_TYPE_GIFT,
        MESSAGE_TYPE_MEMBER: constants.MESSAGE_TYPE_MEMBER,
        MESSAGE_TYPE_SUPER_CHAT: constants.MESSAGE_TYPE_SUPER_CHAT,

        messages: [],
        paidMessages: [],

        messagesBuffer: [],
        preinsertHeight: 0,
        isSmoothed: true,
        chatRateMs: 1000,
        scrollPixelsRemaining: 0,
        scrollTimeRemainingMs: 0,
        lastSmoothChatMessageAddMs: null,
        smoothScrollRafHandle: null,
        lastSmoothScrollUpdate: null,
        membershipPauseUntil: null,
        _pauseTimer: null,
        isCatchingUp: false,
        _catchUpTimer: null,
      }
    },
    mounted() {
      this.scrollToBottom()
    },
    beforeUnmount() {
      this.clearMessages()
    },
    methods: {
      getGiftShowContent(message) {
        return constants.getGiftShowContent(message, this.showGiftName)
      },
      getGiftShowNameAndNum: constants.getGiftShowNameAndNum,
      getShowContent: constants.getShowContent,
      getShowContentParts: constants.getShowContentParts,
      getShowAuthorName: constants.getShowAuthorName,

      mergeSimilarGift(authorName, price, _totalFreeCoin, giftName, num) {
        for (let message of this.iterRecentMessages(5)) {
          if (
            message.type === constants.MESSAGE_TYPE_GIFT
            && message.authorName === authorName
            && message.giftName === giftName
          ) {
            message.price += price
            message.num += num
            return true
          }
        }
        return false
      },
      *iterRecentMessages(num) {
        if (num <= 0) {
          return
        }
        let arrs = [this.messagesBuffer, this.messages]
        for (let arr of arrs) {
          for (let i = arr.length - 1; i >= 0 && num > 0; i--, num--) {
            let message = arr[i]
            yield message
          }
          if (num <= 0) {
            break
          }
        }
      },
      clearMessages() {
        this.messages = []
        this.paidMessages = []
        this.messagesBuffer = []
        this.isSmoothed = true
        this.lastSmoothChatMessageAddMs = null
        this.chatRateMs = 1000
        this.lastSmoothScrollUpdate = null
        this.scrollTimeRemainingMs = this.scrollPixelsRemaining = 0
        this.smoothScrollRafHandle = null
        this.preinsertHeight = 0
        this.membershipPauseUntil = null
        this.isCatchingUp = false
        if (this._pauseTimer) {
          clearTimeout(this._pauseTimer)
          this._pauseTimer = null
        }
        if (this._catchUpTimer) {
          clearTimeout(this._catchUpTimer)
          this._catchUpTimer = null
        }
        this.maybeResizeScrollContainer()
        this.scrollToBottom()
      },

      handleMessageGroup(messageGroup) {
        if (messageGroup.length <= 0) {
          return
        }

        for (let message of messageGroup) {
          switch (message.type) {
          case constants.MESSAGE_TYPE_TEXT:
          case constants.MESSAGE_TYPE_GIFT:
          case constants.MESSAGE_TYPE_MEMBER:
          case constants.MESSAGE_TYPE_SUPER_CHAT:
            this.handleAddMessage(message)
            break
          case constants.MESSAGE_TYPE_DEL:
            this.handleDelMessage(message)
            break
          case constants.MESSAGE_TYPE_UPDATE:
            this.handleUpdateMessage(message)
            break
          }
        }

        this.maybeResizeScrollContainer()
        this.flushMessagesBuffer()
        this.$nextTick(this.maybeScrollToBottom)
      },
      handleAddMessage(message) {
        let isMerged = false
        if (message.type === constants.MESSAGE_TYPE_GIFT) {
          if (this.mergeSimilarGift(message.authorName, message.price, message.totalFreeCoin, message.giftName, message.num)) {
            isMerged = true
          }
        }

        message.addTime = new Date()

        if (message.type !== constants.MESSAGE_TYPE_TEXT) {
          this.paidMessages.unshift(_.cloneDeep(message))
          const MAX_PAID_MESSAGE_NUM = 100
          if (this.paidMessages.length > MAX_PAID_MESSAGE_NUM) {
            this.paidMessages.splice(MAX_PAID_MESSAGE_NUM, this.paidMessages.length - MAX_PAID_MESSAGE_NUM)
          }
        }

        if (!isMerged) {
          this.messagesBuffer.push(message)
        }
      },
      handleDelMessage({ id }) {
        let arrs = [this.messages, this.paidMessages, this.messagesBuffer]
        let needResetSmoothScroll = false
        for (let arr of arrs) {
          for (let i = 0; i < arr.length; i++) {
            if (arr[i].id !== id) {
              continue
            }
            arr.splice(i, 1)
            if (arr === this.messages) {
              needResetSmoothScroll = true
            }
            break
          }
        }
        if (needResetSmoothScroll) {
          this.resetSmoothScroll()
        }
      },
      handleUpdateMessage({ id, newValuesObj }) {
        let arrs = [this.messages, this.paidMessages, this.messagesBuffer]
        let needResetSmoothScroll = false
        for (let arr of arrs) {
          for (let message of arr) {
            if (message.id !== id) {
              continue
            }
            this.doUpdateMessage(message, newValuesObj)
            if (arr === this.messages) {
              needResetSmoothScroll = true
            }
            break
          }
        }
        if (needResetSmoothScroll) {
          this.resetSmoothScroll()
        }
      },
      doUpdateMessage(message, newValuesObj) {
        for (let name in newValuesObj) {
          if (!name.startsWith('$')) {
            message[name] = newValuesObj[name]
          }
        }
      },

      async flushMessagesBuffer() {
        // 正在追播中：消息已进入 buffer，由 catchUpNext 逐个处理
        if (this.isCatchingUp) {
          return
        }

        // 开通会员暂停中：延迟到暂停结束后开始追播
        if (this.membershipPauseUntil) {
          const now = performance.now()
          if (now < this.membershipPauseUntil) {
            if (!this._pauseTimer) {
              this._pauseTimer = setTimeout(() => {
                this._pauseTimer = null
                this.membershipPauseUntil = null
                this.startCatchUp()
              }, this.membershipPauseUntil - now)
            }
            return
          }
          this.membershipPauseUntil = null
        }

        if (this.messagesBuffer.length <= 0) {
          return
        }

        // 检测是否有开通会员消息，计算暂停时长（取最长的）
        let membershipPauseMs = 0
        for (let message of this.messagesBuffer) {
          if (message.type === constants.MESSAGE_TYPE_MEMBER) {
            const durations = { 3: 3000, 2: 8000, 1: 20000 }
            const dur = durations[message.privilegeType] || 3000
            if (dur > membershipPauseMs) {
              membershipPauseMs = dur
            }
          }
        }

        // 正常模式：全部刷新
        let removeNum = Math.max(this.messages.length + this.messagesBuffer.length - this.maxNumber, 0)
        if (removeNum > 0) {
          this.messages.splice(0, removeNum)
          await this.$nextTick()
        }

        this.preinsertHeight = this.$refs.items.clientHeight
        for (let message of this.messagesBuffer) {
          this.messages.push(message)
        }
        this.messagesBuffer = []
        await this.$nextTick()
        this.showNewMessages()

        // 有开通会员时进入暂停
        if (membershipPauseMs > 0) {
          this.membershipPauseUntil = performance.now() + membershipPauseMs
        }
      },

      // 追播模式：逐个回放暂停期间积压的消息
      startCatchUp() {
        if (this.isCatchingUp || this.messagesBuffer.length <= 0) {
          this.isCatchingUp = false
          return
        }
        this.isCatchingUp = true
        this.catchUpNext()
      },

      async catchUpNext() {
        if (this.messagesBuffer.length <= 0) {
          this.isCatchingUp = false
          return
        }

        // 取队首一条消息
        const message = this.messagesBuffer.shift()

        // 检测是否为开通会员，计算暂停时长
        // 舰长:3秒, 提督:8秒, 总督:20秒
        if (message.type === constants.MESSAGE_TYPE_MEMBER) {
          const durations = { 3: 3000, 2: 8000, 1: 20000 }
          const pauseMs = durations[message.privilegeType] || 3000

          // 显示这条会员消息
          let removeNum = Math.max(this.messages.length + 1 - this.maxNumber, 0)
          if (removeNum > 0) {
            this.messages.splice(0, removeNum)
            await this.$nextTick()
          }

          this.preinsertHeight = this.$refs.items.clientHeight
          this.messages.push(message)
          await this.$nextTick()
          this.showNewMessages()

          // 停止追播，进入暂停
          this.isCatchingUp = false
          this.membershipPauseUntil = performance.now() + pauseMs
          return
        }

        // 普通消息：显示后继续追播下一条
        let removeNum = Math.max(this.messages.length + 1 - this.maxNumber, 0)
        if (removeNum > 0) {
          this.messages.splice(0, removeNum)
          await this.$nextTick()
        }

        this.preinsertHeight = this.$refs.items.clientHeight
        this.messages.push(message)
        await this.$nextTick()
        this.showNewMessages()

        // 按正常弹幕速率继续追播
        this._catchUpTimer = setTimeout(() => {
          this._catchUpTimer = null
          this.catchUpNext()
        }, this.isSmoothed ? 200 : 80)
      },
      showNewMessages() {
        let hasScrollBar = this.$refs.items.clientHeight > this.$refs.scroller.clientHeight
        this.$refs.itemOffset.style.height = this.$refs.items.clientHeight + 'px'
        if (!hasScrollBar) {
          return
        }

        this.scrollPixelsRemaining += this.$refs.items.clientHeight - this.preinsertHeight
        this.scrollToBottom()

        if (!this.lastSmoothChatMessageAddMs) {
          this.lastSmoothChatMessageAddMs = performance.now()
        }
        let interval = performance.now() - this.lastSmoothChatMessageAddMs
        this.chatRateMs = (0.9 * this.chatRateMs) + (0.1 * interval)
        if (this.isSmoothed) {
          if (this.chatRateMs < 400) {
            this.isSmoothed = false
          }
        } else {
          if (this.chatRateMs > 450) {
            this.isSmoothed = true
          }
        }
        this.scrollTimeRemainingMs += this.isSmoothed ? CHAT_SMOOTH_ANIMATION_TIME_MS : 0

        if (!this.smoothScrollRafHandle) {
          this.smoothScrollRafHandle = window.requestAnimationFrame(this.smoothScroll)
        }
        this.lastSmoothChatMessageAddMs = performance.now()
      },
      smoothScroll(time) {
        if (!this.lastSmoothScrollUpdate) {
          this.lastSmoothScrollUpdate = time
          this.smoothScrollRafHandle = window.requestAnimationFrame(this.smoothScroll)
          return
        }

        let interval = time - this.lastSmoothScrollUpdate
        if (
          this.scrollPixelsRemaining <= 0 || this.scrollPixelsRemaining >= 400
          || interval >= 1000
          || this.scrollTimeRemainingMs <= 0
        ) {
          this.resetSmoothScroll()
          return
        }

        let pixelsToScroll = interval / this.scrollTimeRemainingMs * this.scrollPixelsRemaining
        this.scrollPixelsRemaining -= pixelsToScroll
        if (this.scrollPixelsRemaining < 0) {
          this.scrollPixelsRemaining = 0
        }
        this.scrollTimeRemainingMs -= interval
        if (this.scrollTimeRemainingMs < 0) {
          this.scrollTimeRemainingMs = 0
        }
        this.lastSmoothScrollUpdate = time
        this.smoothScrollRafHandle = window.requestAnimationFrame(this.smoothScroll)
      },
      resetSmoothScroll() {
        this.scrollTimeRemainingMs = this.scrollPixelsRemaining = 0
        this.lastSmoothScrollUpdate = null
        if (this.smoothScrollRafHandle) {
          window.cancelAnimationFrame(this.smoothScrollRafHandle)
          this.smoothScrollRafHandle = null
        }
      },

      maybeResizeScrollContainer() {
        this.$refs.itemOffset.style.height = this.$refs.items.clientHeight + 'px'
        this.$refs.itemOffset.style.minHeight = this.$refs.scroller.clientHeight + 'px'
        this.maybeScrollToBottom()
      },
      maybeScrollToBottom() {
        this.scrollToBottom()
      },
      scrollToBottom() {
        this.$refs.scroller.scrollTop = Math.pow(2, 24)
      },
    }
  }

  return exports
}))
