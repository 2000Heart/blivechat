(function(root, factory) {
  root.chatRendererTicker = factory(
    root.chatRendererConstants,
    root.chatRendererImgShadow.default,
    root.liquidGlassLiquidGlass.default,
  )
}(this,
/**
 * @import * as constants from './constants'
 * @import * as ImgShadow from './ImgShadow'
 * @import LiquidGlass from './liquid-glass/LiquidGlass'
 * @param {typeof constants} constants
 * @param {typeof ImgShadow.default} ImgShadow
 * @param {typeof LiquidGlass.default} LiquidGlass
 */
function(constants, ImgShadow, LiquidGlass) {
  const exports = {}

  exports.default = {
    template: `
  <lg-live-chat-ticker-renderer :hidden="showMessages.length === 0">
    <transition-group tag="div" :css="false" @enter="onTickerItemEnter" @leave="onTickerItemLeave"
      id="items" class="style-scope lg-live-chat-ticker-renderer"
    >
      <lg-live-chat-ticker-paid-message-item-renderer v-for="message in showMessages" :key="message.raw.id"
        tabindex="0" class="style-scope lg-live-chat-ticker-renderer" style="overflow: hidden;"
        :data-price-level="message.priceLevel"
      >
        <LiquidGlass
          :displacementScale="55"
          :blurAmount="0.06"
          :saturation="170"
          :aberrationIntensity="1.8"
          :cornerRadius="8"
          :padding="'6px 12px'"
          :mode="'standard'"
          :overLight="message.priceLevel >= 5"
          :elasticity="0"
          style="position: relative; width: auto; display: inline-flex; white-space: nowrap;"
        >
          <img-shadow id="author-photo" height="20" width="20" class="style-scope lg-live-chat-ticker-paid-message-item-renderer"
            :imgUrl="message.raw.avatarUrl"
          ></img-shadow>
          <span id="text" dir="ltr" class="style-scope lg-live-chat-ticker-paid-message-item-renderer" :style="{
            color: message.color
          }">{{ message.text }}</span>
        </LiquidGlass>
      </lg-live-chat-ticker-paid-message-item-renderer>
    </transition-group>
  </lg-live-chat-ticker-renderer>
    `,
    name: 'Ticker',
    components: {
      ImgShadow,
      LiquidGlass
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
          let priceConfig = message.type === constants.MESSAGE_TYPE_MEMBER 
            ? null 
            : constants.getPriceConfig(message.price)
          res.push({
            raw: message,
            color: this.getColor(message),
            text: this.getText(message),
            priceLevel: priceConfig ? priceConfig.priceLevel : 0
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
          // CSS指定了不显示固定栏
          done()
          return
        }
        el.style.width = 0
        await this.$nextTick()
        el.style.width = `${width}px`
        window.setTimeout(done, 200)
      },
      onTickerItemLeave(el, done) {
        el.classList.add('sliding-down')
        window.setTimeout(() => {
          el.classList.add('collapsing')
          el.style.width = 0
          window.setTimeout(() => {
            el.classList.remove('sliding-down')
            el.classList.remove('collapsing')
            el.style.width = 'auto'
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
        let config = constants.getPriceConfig(message.price)
        // 使用更柔和的颜色，确保在液态玻璃上可见
        if (config.priceLevel === 0) {
          return 'rgba(153, 236, 255, 0.9)'
        } else if (config.priceLevel === 1) {
          return 'rgba(30, 136, 229, 0.9)'
        } else if (config.priceLevel === 2) {
          return 'rgba(0, 229, 255, 0.9)'
        } else if (config.priceLevel === 3) {
          return 'rgba(29, 233, 182, 0.9)'
        } else if (config.priceLevel === 4) {
          return 'rgba(255, 202, 40, 0.9)'
        } else if (config.priceLevel === 5) {
          return 'rgba(245, 124, 0, 0.9)'
        } else if (config.priceLevel === 6) {
          return 'rgba(233, 30, 99, 0.9)'
        } else {
          return 'rgba(230, 33, 23, 0.9)'
        }
      },
      getText(message) {
        if (message.type === constants.MESSAGE_TYPE_MEMBER) {
          return '会员'
        }
        return `CN¥${constants.formatCurrency(message.price)}`
      },
      getDecorationGradient(message) {
        if (message.type === constants.MESSAGE_TYPE_MEMBER) {
          return 'linear-gradient(135deg, rgba(15, 157, 88, 0.8), rgba(33, 150, 243, 0.8))'
        }
        let config = constants.getPriceConfig(message.price)
        if (config.priceLevel === 0) {
          return 'linear-gradient(135deg, rgba(153, 236, 255, 0.8), rgba(30, 136, 229, 0.8))'
        } else if (config.priceLevel === 1) {
          return 'linear-gradient(135deg, rgba(30, 136, 229, 0.8), rgba(0, 229, 255, 0.8))'
        } else if (config.priceLevel === 2) {
          return 'linear-gradient(135deg, rgba(0, 229, 255, 0.8), rgba(29, 233, 182, 0.8))'
        } else if (config.priceLevel === 3) {
          return 'linear-gradient(135deg, rgba(29, 233, 182, 0.8), rgba(255, 202, 40, 0.8))'
        } else if (config.priceLevel === 4) {
          return 'linear-gradient(135deg, rgba(255, 202, 40, 0.8), rgba(245, 124, 0, 0.8))'
        } else if (config.priceLevel === 5) {
          return 'linear-gradient(135deg, rgba(245, 124, 0, 0.8), rgba(233, 30, 99, 0.8))'
        } else if (config.priceLevel === 6) {
          return 'linear-gradient(135deg, rgba(233, 30, 99, 0.8), rgba(230, 33, 23, 0.8))'
        } else {
          return 'linear-gradient(135deg, rgba(230, 33, 23, 0.8), rgba(255, 0, 0, 0.8))'
        }
      },
      getPinTime(message) {
        if (message.type === constants.MESSAGE_TYPE_MEMBER) {
          return 2
        }
        return constants.getPriceConfig(message.price).pinTime
      },
      updateProgress() {
        // 更新进度
        this.curTime = new Date()

        // 删除过期的消息
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
