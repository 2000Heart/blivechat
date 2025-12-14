(function(root, factory) {
  root.chatRendererPaidMessage = factory(
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
  <lg-live-chat-paid-message-renderer class="style-scope lg-live-chat-item-list-renderer" allow-animations
    :style="{
      '--lg-paid-message-color': color.content
    }"
    :blc-price-level="priceConfig.priceLevel"
  >
    <LiquidGlass
      :displacementScale="60"
      :blurAmount="0.08"
      :saturation="180"
      :aberrationIntensity="2"
      :cornerRadius="12"
      :padding="'16px 20px'"
      :mode="'standard'"
      :overLight="priceConfig.priceLevel >= 5"
      :elasticity="0"
      style="position: relative; width: auto; display: inline-block;"
    >
      <div class="paid-header">
        <img-shadow id="author-photo" height="24" width="24" class="style-scope lg-live-chat-paid-message-renderer"
          :imgUrl="avatarUrl"
        ></img-shadow>
        <span id="author-name" class="style-scope lg-live-chat-paid-message-renderer">{{ authorName }}</span>
        <span v-if="medalName && medalLevel > 0" id="medal" class="style-scope lg-live-chat-paid-message-renderer" :data-level="medalLevel">
          <span class="medal-name">{{ medalName }}</span>
          <span class="medal-level">{{ medalLevel }}</span>
        </span>
        <span v-if="giftName" id="gift-info" class="style-scope lg-live-chat-paid-message-renderer" :data-price-high="price >= 100">
          <span id="gift-name" class="style-scope lg-live-chat-paid-message-renderer">{{ giftName }}</span>
          <span v-if="giftNum > 1" id="gift-num" class="style-scope lg-live-chat-paid-message-renderer">x{{ giftNum }}</span>
          <span v-if="price > 0" id="gift-price" class="style-scope lg-live-chat-paid-message-renderer">{{ showGiftPriceText }}</span>
        </span>
        <span v-if="!isGift" id="purchase-amount" class="style-scope lg-live-chat-paid-message-renderer">{{ showPriceText }}</span>
        <span id="timestamp" class="style-scope lg-live-chat-paid-message-renderer">{{ timeText }}</span>
      </div>
      <span v-if="content" id="message" dir="auto" class="style-scope lg-live-chat-paid-message-renderer">{{ content }}</span>
    </LiquidGlass>
  </lg-live-chat-paid-message-renderer>
    `,
    name: 'PaidMessage',
    components: {
      ImgShadow,
      LiquidGlass
    },
    props: {
      avatarUrl: String,
      authorName: String,
      price: Number, // 价格，人民币
      priceText: String,
      time: Date,
      content: String,
      medalLevel: Number,
      medalName: String,
      giftName: String,
      giftNum: Number
    },
    computed: {
      isGift() {
        return !!this.giftName
      },
      priceConfig() {
        return constants.getPriceConfig(this.price)
      },
      color() {
        return this.priceConfig.colors
      },
      showPriceText() {
        return this.priceText || `CN¥${constants.formatCurrency(this.price)}`
      },
      showGiftPriceText() {
        return `CN¥${constants.formatCurrency(this.price)}`
      },
      timeText() {
        return constants.getTimeTextHourMin(this.time)
      }
    }
  }

  return exports
}))
