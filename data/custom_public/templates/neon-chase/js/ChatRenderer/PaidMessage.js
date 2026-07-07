(function(root, factory) {
  root.chatRendererPaidMessage = factory(
    root.chatRendererConstants,
    root.chatRendererImgShadow.default,
    root.chatRendererAuthorChip.default,
  )
}(this,
function(constants, ImgShadow, AuthorChip) {
  const exports = {}

  exports.default = {
    template: `
  <nc-live-chat-paid-message-renderer>
    <div class="paid-header">
      <img-shadow id="author-photo" height="24" width="24"
        :imgUrl="avatarUrl"
      ></img-shadow>
      <author-chip
        :authorName="authorName" :authorType="authorType" :privilegeType="privilegeType"
        :medalLevel="medalLevel" :medalName="medalName"
      ></author-chip>
      <span id="timestamp">{{ timeText }}</span>
    </div>
    <div class="nc-bubble nc-breathe" :class="breatheClass">
      <div class="nc-bubble-inner">
        <span id="message" v-if="content && !isGift">{{ content }}</span>
        <span v-if="giftName" id="gift-info">
          <span id="gift-name">{{ giftName }}</span>
          <span v-if="giftNum > 1" id="gift-num">x{{ giftNum }}</span>
        </span>
        <span id="purchase-amount" v-if="price > 0">{{ showPriceText }}</span>
      </div>
    </div>
  </nc-live-chat-paid-message-renderer>
    `,
    name: 'PaidMessage',
    components: {
      ImgShadow,
      AuthorChip,
    },
    props: {
      avatarUrl: String,
      authorName: String,
      authorType: Number,
      privilegeType: Number,
      price: Number,
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
      breatheClass() {
        if (this.price <= 0) {
          return 'free-gift'
        }
        if (this.price >= 100) {
          return 'large-sc'
        }
        return 'paid-gift'
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
