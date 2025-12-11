(function(root, factory) {
  root.chatRendererConstants = factory(root.blcsdk)
}(this,
/**
 * @import * as blcsdk from '../vendor/blcsdk'
 * @param {typeof blcsdk} blcsdk
 */
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

  const EXCHANGE_RATE = 7
  const PRICE_CONFIGS = [
    {
      price: 0,
      colors: {
        contentBg: 'rgba(0, 122, 255, 0.2)',
        headerBg: 'rgba(0, 122, 255, 0.3)',
        header: 'rgba(255,255,255,1)',
        authorName: 'rgba(255,255,255,0.9)',
        time: 'rgba(255,255,255,0.6)',
        content: 'rgba(255,255,255,1)'
      },
      pinTime: 0,
      priceLevel: 0,
    },
    {
      price: 0.01,
      colors: {
        contentBg: 'rgba(0, 122, 255, 0.25)',
        headerBg: 'rgba(0, 122, 255, 0.35)',
        header: 'rgba(255,255,255,1)',
        authorName: 'rgba(255,255,255,0.9)',
        time: 'rgba(255,255,255,0.6)',
        content: 'rgba(255,255,255,1)'
      },
      pinTime: 0,
      priceLevel: 1,
    },
    {
      price: 2 * EXCHANGE_RATE,
      colors: {
        contentBg: 'rgba(0, 153, 255, 0.3)',
        headerBg: 'rgba(0, 122, 255, 0.4)',
        header: 'rgba(255,255,255,1)',
        authorName: 'rgba(255,255,255,0.9)',
        time: 'rgba(255,255,255,0.6)',
        content: 'rgba(255,255,255,1)'
      },
      pinTime: 0,
      priceLevel: 2,
    },
    {
      price: 5 * EXCHANGE_RATE,
      colors: {
        contentBg: 'rgba(0, 122, 255, 0.35)',
        headerBg: 'rgba(0, 122, 255, 0.45)',
        header: 'rgba(255,255,255,1)',
        authorName: 'rgba(255,255,255,0.9)',
        time: 'rgba(255,255,255,0.6)',
        content: 'rgba(255,255,255,1)'
      },
      pinTime: 2,
      priceLevel: 3,
    },
    {
      price: 10 * EXCHANGE_RATE,
      colors: {
        contentBg: 'rgba(0, 122, 255, 0.4)',
        headerBg: 'rgba(0, 122, 255, 0.5)',
        header: 'rgba(255,255,255,1)',
        authorName: 'rgba(255,255,255,0.9)',
        time: 'rgba(255,255,255,0.6)',
        content: 'rgba(255,255,255,1)'
      },
      pinTime: 5,
      priceLevel: 4,
    },
    {
      price: 20 * EXCHANGE_RATE,
      colors: {
        contentBg: 'rgba(0, 122, 255, 0.45)',
        headerBg: 'rgba(0, 122, 255, 0.55)',
        header: 'rgba(255,255,255,1)',
        authorName: 'rgba(255,255,255,0.9)',
        time: 'rgba(255,255,255,0.6)',
        content: 'rgba(255,255,255,1)'
      },
      pinTime: 10,
      priceLevel: 5,
    },
    {
      price: 50 * EXCHANGE_RATE,
      colors: {
        contentBg: 'rgba(0, 122, 255, 0.5)',
        headerBg: 'rgba(0, 122, 255, 0.6)',
        header: 'rgba(255,255,255,1)',
        authorName: 'rgba(255,255,255,0.9)',
        time: 'rgba(255,255,255,0.6)',
        content: 'rgba(255,255,255,1)'
      },
      pinTime: 30,
      priceLevel: 6,
    },
    {
      price: 100 * EXCHANGE_RATE,
      colors: {
        contentBg: 'rgba(0, 122, 255, 0.6)',
        headerBg: 'rgba(0, 122, 255, 0.7)',
        header: 'rgba(255,255,255,1)',
        authorName: 'rgba(255,255,255,0.9)',
        time: 'rgba(255,255,255,0.6)',
        content: 'rgba(255,255,255,1)'
      },
      pinTime: 60,
      priceLevel: 7,
    },
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

