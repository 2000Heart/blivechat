(function(root, factory) {
  root.chatRendererTextMessage = factory(
    root.chatRendererConstants,
    root.chatRendererImgShadow.default,
    root.chatRendererAuthorChip.default,
  )
}(this,
function(constants, ImgShadow, AuthorChip) {
  const exports = {}

  exports.default = {
    template: `
  <nc-live-chat-text-message-renderer>
    <div class="nc-author-row">
      <img-shadow id="author-photo" height="24" width="24"
        :imgUrl="avatarUrl"
      ></img-shadow>
      <span class="nc-ts">{{ timeText }}</span>
      <author-chip
        :authorName="authorName" :authorType="authorType" :privilegeType="privilegeType"
        :medalLevel="medalLevel" :medalName="medalName"
      ></author-chip>
    </div>
    <div class="nc-bubble" :class="bubbleClass">
      <div class="nc-bubble-inner">
        <span id="message">
          <template v-for="(content, index) in contentParts">
            <span :key="'text-' + index" v-if="content.type === CONTENT_PART_TYPE_TEXT">{{ content.text }}</span>
            <img :key="'img-' + index" v-else-if="content.type === CONTENT_PART_TYPE_IMAGE"
              class="emoji"
              :src="content.url" :alt="content.text"
              :width="content.width" :height="content.height"
              :class="{ 'blc-large-emoji': content.height >= 100 }"
            >
          </template>
        </span>
      </div>
    </div>
  </nc-live-chat-text-message-renderer>
    `,
    name: 'TextMessage',
    components: {
      ImgShadow,
      AuthorChip,
    },
    props: {
      avatarUrl: String,
      time: Date,
      authorName: String,
      authorType: Number,
      contentParts: Array,
      privilegeType: Number,
      medalLevel: Number,
      medalName: String
    },
    data() {
      return {
        CONTENT_PART_TYPE_TEXT: constants.CONTENT_PART_TYPE_TEXT,
        CONTENT_PART_TYPE_IMAGE: constants.CONTENT_PART_TYPE_IMAGE
      }
    },
    computed: {
      timeText() {
        return constants.getTimeTextHourMin(this.time)
      },
      bubbleClass() {
        // 大航海身份优先：有 privilegeType 就用追光动画
        switch (this.privilegeType) {
          case 1: return 'nc-chase-dual gov'
          case 2: return 'nc-chase commander'
          case 3: return 'nc-chase sailor'
        }
        // 非大航海才判断基础用户类型
        if (this.authorType === constants.AUTHOR_TYPE_ADMIN) {
          return 'nc-static admin'
        }
        if (this.authorType === constants.AUTHOR_TYPE_OWNER) {
          return 'nc-static owner'
        }
        return 'nc-static user'
      }
    }
  }

  return exports
}))
