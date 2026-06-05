(function(root, factory) {
  root.chatRenderer = factory(
    root._,
    root.chatRendererConstants,
    root.chatRendererTextMessage.default,
    root.chatRendererPaidMessage.default,
    root.chatRendererMembershipItem.default,
    root.chatRendererTicker.default,
  )
}(this,
function(_, constants, TextMessage, PaidMessage, MembershipItem, Ticker) {
  const exports = {}

  const CHAT_SMOOTH_ANIMATION_TIME_MS = 84

  exports.default = {
    template: `
  <nc-live-chat-renderer style="--scrollbar-width:11px;">
    <ticker class="style-scope nc-live-chat-renderer" v-model:messages="paidMessages" :showGiftName="showGiftName"></ticker>
    <nc-live-chat-item-list-renderer allow-scroll>
      <div ref="scroller" id="item-scroller" class="style-scope nc-live-chat-item-list-renderer animated">
        <div ref="itemOffset" id="item-offset" class="style-scope nc-live-chat-item-list-renderer">
          <div ref="items" id="items" class="style-scope nc-live-chat-item-list-renderer" style="overflow: hidden"
            :style="{ transform: 'translateY(' + Math.floor(scrollPixelsRemaining) + 'px)' }"
          >
            <template v-for="message in messages">
              <text-message :key="'text-' + message.id" v-if="message.type === MESSAGE_TYPE_TEXT"
                :time="message.time"
                :avatarUrl="message.avatarUrl"
                :authorName="message.authorName"
                :authorType="message.authorType"
                :privilegeType="message.privilegeType"
                :contentParts="getShowContentParts(message)"
                :medalLevel="message.medalLevel"
                :medalName="message.medalName"
              ></text-message>
              <paid-message :key="'gift-' + message.id" v-else-if="message.type === MESSAGE_TYPE_GIFT"
                :time="message.time"
                :avatarUrl="message.avatarUrl"
                :authorName="getShowAuthorName(message)"
                :price="message.price"
                :priceText="''"
                :content="message.price <= 0 ? '' : getGiftShowContent(message)"
                :medalLevel="message.medalLevel"
                :medalName="message.medalName"
                :giftName="message.giftName"
                :giftNum="message.num"
              ></paid-message>
              <membership-item :key="'member-' + message.id" v-else-if="message.type === MESSAGE_TYPE_MEMBER"
                :time="message.time"
                :avatarUrl="message.avatarUrl"
                :authorName="getShowAuthorName(message)"
                :privilegeType="message.privilegeType"
                :title="message.title"
                :medalLevel="message.medalLevel"
                :medalName="message.medalName"
              ></membership-item>
              <paid-message :key="'sc-' + message.id" v-else-if="message.type === MESSAGE_TYPE_SUPER_CHAT"
                :time="message.time"
                :avatarUrl="message.avatarUrl"
                :authorName="getShowAuthorName(message)"
                :price="message.price"
                :content="getShowContent(message)"
                :medalLevel="message.medalLevel"
                :medalName="message.medalName"
              ></paid-message>
            </template>
          </div>
        </div>
      </div>
    </nc-live-chat-item-list-renderer>
  </nc-live-chat-renderer>
    `,
    name: 'ChatRenderer',
    components: {
      Ticker,
      TextMessage,
      MembershipItem,
      PaidMessage
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
        if (this.messagesBuffer.length <= 0) {
          return
        }

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
