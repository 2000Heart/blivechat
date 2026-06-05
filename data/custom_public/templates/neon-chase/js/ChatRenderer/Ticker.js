(function(root, factory) {
  root.chatRendererTicker = factory(
    root.chatRendererConstants,
    root.chatRendererImgShadow.default,
  )
}(this,
function(constants, ImgShadow) {
  const exports = {}

  exports.default = {
    template: `
  <nc-live-chat-ticker-renderer :hidden="showMessages.length === 0">
    <transition-group tag="div" :css="false" @enter="onTickerItemEnter" @leave="onTickerItemLeave"
      id="items" class="style-scope nc-live-chat-ticker-renderer"
    >
      <nc-live-chat-ticker-paid-message-item-renderer v-for="message in showMessages" :key="message.raw.id"
        tabindex="0" style="overflow: hidden;"
        :style="{ background: message.bgColor }"
      >
        <img-shadow id="author-photo" height="20" width="20"
          :imgUrl="message.raw.avatarUrl"
        ></img-shadow>
        <span id="text" :style="{ color: message.color }">{{ message.text }}</span>
      </nc-live-chat-ticker-paid-message-item-renderer>
    </transition-group>
  </nc-live-chat-ticker-renderer>
    `,
    name: 'Ticker',
    components: {
      ImgShadow,
    },
    props: {
      messages: Array,
      showGiftName: Boolean
    },
    data() {
      return {
        MESSAGE_TYPE_MEMBER: constants.MESSAGE_TYPE_MEMBER,
        curTime: new Date(),
        updateTimerId: window.setInterval(this.updateProgress, 1000),
      }
    },
    computed: {
      showMessages() {
        let res = []
        for (let message of this.messages) {
          if (!this.needToShow(message)) {
            continue
          }
          res.push({
            raw: message,
            color: this.getColor(message),
            bgColor: this.getBgColor(message),
            text: this.getText(message),
          })
        }
        return res
      },
    },
    beforeUnmount() {
      window.clearInterval(this.updateTimerId)
    },
    methods: {
      async onTickerItemEnter(el, done) {
        let width = el.clientWidth
        if (width === 0) {
          done()
          return
        }
        el.style.width = '0px'
        await this.$nextTick()
        el.style.width = width + 'px'
        window.setTimeout(done, 200)
      },
      onTickerItemLeave(el, done) {
        el.classList.add('sliding-down')
        window.setTimeout(() => {
          el.classList.add('collapsing')
          el.style.width = '0px'
          window.setTimeout(() => {
            el.classList.remove('sliding-down')
            el.classList.remove('collapsing')
            done()
          }, 200)
        }, 200)
      },

      needToShow(message) {
        let pinTime = this.getPinTime(message)
        return (new Date() - message.addTime) / (60 * 1000) < pinTime
      },
      getColor(message) {
        if (message.type === constants.MESSAGE_TYPE_MEMBER) {
          return 'rgba(15, 157, 88, 0.9)'
        }
        if (message.price <= 0) return 'rgba(153, 236, 255, 0.9)'
        if (message.price < 100) return 'rgba(255, 202, 40, 0.9)'
        return 'rgba(255, 23, 68, 0.9)'
      },
      getBgColor(message) {
        if (message.type === constants.MESSAGE_TYPE_MEMBER) {
          return 'linear-gradient(135deg, rgba(15, 157, 88, 0.3), rgba(33, 150, 243, 0.3))'
        }
        if (message.price <= 0) return 'linear-gradient(135deg, rgba(0, 229, 255, 0.2), rgba(30, 136, 229, 0.2))'
        if (message.price < 100) return 'linear-gradient(135deg, rgba(255, 215, 0, 0.2), rgba(255, 160, 0, 0.2))'
        return 'linear-gradient(135deg, rgba(255, 23, 68, 0.2), rgba(255, 0, 0, 0.2))'
      },
      getText(message) {
        if (message.type === constants.MESSAGE_TYPE_MEMBER) {
          return '会员'
        }
        return `CN¥${constants.formatCurrency(message.price)}`
      },
      getPinTime(message) {
        if (message.type === constants.MESSAGE_TYPE_MEMBER) {
          return 2
        }
        return constants.getPriceConfig(message.price).pinTime
      },
      updateProgress() {
        this.curTime = new Date()
        let filteredMessages = []
        let messagesChanged = false
        for (let message of this.messages) {
          let pinTime = this.getPinTime(message)
          if ((this.curTime - message.addTime) / (60 * 1000) >= pinTime) {
            messagesChanged = true
            continue
          }
          filteredMessages.push(message)
        }
        if (messagesChanged) {
          this.$emit('update:messages', filteredMessages)
        }
      },
    }
  }

  return exports
}))
