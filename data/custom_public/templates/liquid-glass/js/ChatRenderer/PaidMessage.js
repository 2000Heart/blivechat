(function(root, factory) {
  root.chatRendererPaidMessage = factory(
    root.chatRendererConstants,
    root.chatRendererImgShadow.default,
  )
}(this,
/**
 * @import * as constants from './constants'
 * @import * as ImgShadow from './ImgShadow'
 * @param {typeof constants} constants
 * @param {typeof ImgShadow.default} ImgShadow
 */
function(constants, ImgShadow) {
  const exports = {}

  exports.default = {
    template: `
  <lg-live-chat-paid-message-renderer class="style-scope lg-live-chat-item-list-renderer" allow-animations
    :style="{
      '--lg-paid-message-color': color.content
    }"
    :blc-price-level="priceConfig.priceLevel"
  >
    <div class="liquidGlass-wrapper">
      <div class="liquidGlass-effect"></div>
      <div class="liquidGlass-tint"></div>
      <div class="liquidGlass-shine"></div>
      <div class="liquidGlass-text">
        <div class="paid-decoration"></div>
        <div class="paid-header">
          <img-shadow id="author-photo" height="24" width="24" class="style-scope lg-live-chat-paid-message-renderer"
            :imgUrl="avatarUrl"
          ></img-shadow>
          <span id="author-name" class="style-scope lg-live-chat-paid-message-renderer">{{ authorName }}</span>
          <span id="purchase-amount" class="style-scope lg-live-chat-paid-message-renderer">{{ showPriceText }}</span>
          <span id="timestamp" class="style-scope lg-live-chat-paid-message-renderer">{{ timeText }}</span>
        </div>
        <span v-if="content" id="message" dir="auto" class="style-scope lg-live-chat-paid-message-renderer">{{ content }}</span>
      </div>
    </div>
  </lg-live-chat-paid-message-renderer>
    `,
    name: 'PaidMessage',
    components: {
      ImgShadow
    },
    props: {
      avatarUrl: String,
      authorName: String,
      price: Number, // 价格，人民币
      priceText: String,
      time: Date,
      content: String
    },
    computed: {
      priceConfig() {
        return constants.getPriceConfig(this.price)
      },
      color() {
        return this.priceConfig.colors
      },
      showPriceText() {
        return this.priceText || `CN¥${constants.formatCurrency(this.price)}`
      },
      timeText() {
        return constants.getTimeTextHourMin(this.time)
      }
    }
  }

  return exports
}))
