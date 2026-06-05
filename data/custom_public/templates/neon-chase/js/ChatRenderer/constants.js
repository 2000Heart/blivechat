(function(root, factory) {
  root.chatRendererConstants = factory(root.blcsdk)
}(this,
function(blcsdk) {
  const exports = {}

  exports.AUTHOR_TYPE_NORMAL = blcsdk.AuthorType.NORMAL
  exports.AUTHOR_TYPE_MEMBER = blcsdk.AuthorType.MEMBER
  exports.AUTHOR_TYPE_ADMIN = blcsdk.AuthorType.ADMIN
  exports.AUTHOR_TYPE_OWNER = blcsdk.AuthorType.OWNER

  const AUTHOR_TYPE_TO_TEXT = []
  AUTHOR_TYPE_TO_TEXT[blcsdk.AuthorType.NORMAL] = ''
  AUTHOR_TYPE_TO_TEXT[blcsdk.AuthorType.MEMBER] = 'member'
  AUTHOR_TYPE_TO_TEXT[blcsdk.AuthorType.ADMIN] = 'moderator'
  AUTHOR_TYPE_TO_TEXT[blcsdk.AuthorType.OWNER] = 'owner'
  exports.AUTHOR_TYPE_TO_TEXT = AUTHOR_TYPE_TO_TEXT

  const GUARD_LEVEL_TO_TEXT_KEY = []
  GUARD_LEVEL_TO_TEXT_KEY[blcsdk.GuardLevel.NONE] = ''
  GUARD_LEVEL_TO_TEXT_KEY[blcsdk.GuardLevel.LV3] = '总督'
  GUARD_LEVEL_TO_TEXT_KEY[blcsdk.GuardLevel.LV2] = '提督'
  GUARD_LEVEL_TO_TEXT_KEY[blcsdk.GuardLevel.LV1] = '舰长'

  exports.getShowGuardLevelText = function(guardLevel) {
    return GUARD_LEVEL_TO_TEXT_KEY[guardLevel] || ''
  }

  exports.MESSAGE_TYPE_TEXT = blcsdk.MsgType.TEXT
  exports.MESSAGE_TYPE_GIFT = blcsdk.MsgType.GIFT
  exports.MESSAGE_TYPE_MEMBER = blcsdk.MsgType.MEMBER
  exports.MESSAGE_TYPE_SUPER_CHAT = blcsdk.MsgType.SUPER_CHAT
  exports.MESSAGE_TYPE_DEL = 30
  exports.MESSAGE_TYPE_UPDATE = 31

  exports.CONTENT_PART_TYPE_TEXT = blcsdk.ContentPartType.TEXT
  exports.CONTENT_PART_TYPE_IMAGE = blcsdk.ContentPartType.IMAGE

  // 价格等级配置（仅用于价格判断）
  const PRICE_CONFIGS = [
    { price: 0, pinTime: 0, priceLevel: 0 },
    { price: 0.01, pinTime: 0, priceLevel: 1 },
    { price: 14, pinTime: 0, priceLevel: 2 },
    { price: 35, pinTime: 2, priceLevel: 3 },
    { price: 70, pinTime: 5, priceLevel: 4 },
    { price: 140, pinTime: 10, priceLevel: 5 },
    { price: 350, pinTime: 30, priceLevel: 6 },
    { price: 700, pinTime: 60, priceLevel: 7 },
  ]

  exports.getPriceConfig = function(price) {
    let i = 0
    for (; i < PRICE_CONFIGS.length - 1; i++) {
      let nextConfig = PRICE_CONFIGS[i + 1]
      if (price < nextConfig.price) {
        return PRICE_CONFIGS[i]
      }
    }
    return PRICE_CONFIGS[i]
  }

  exports.getShowContent = function(message) {
    if (message.translation) {
      return `${message.content}（${message.translation}）`
    }
    return message.content
  }

  exports.getShowContentParts = function(message) {
    let contentParts = [...message.contentParts]
    if (message.translation) {
      contentParts.push({
        type: blcsdk.ContentPartType.TEXT,
        text: `（${message.translation}）`
      })
    }
    return contentParts
  }

  exports.getGiftShowContent = function(message, showGiftName) {
    if (!showGiftName) {
      return ''
    }
    return `赠送 ${message.giftName}x${message.num}`
  }

  exports.getGiftShowNameAndNum = function(message) {
    return `${message.giftName}x${message.num}`
  }

  exports.getShowAuthorName = function(message) {
    if (message.authorNamePronunciation && message.authorNamePronunciation !== message.authorName) {
      return `${message.authorName}(${message.authorNamePronunciation})`
    }
    return message.authorName
  }

  exports.getTimeTextHourMin = function(date) {
    let hour = date.getHours()
    let min = `00${date.getMinutes()}`.slice(-2)
    return `${hour}:${min}`
  }

  exports.formatCurrency = function(price) {
    return new Intl.NumberFormat('zh-CN', {
      minimumFractionDigits: price < 100 ? 2 : 0
    }).format(price)
  }

  return exports
}))
