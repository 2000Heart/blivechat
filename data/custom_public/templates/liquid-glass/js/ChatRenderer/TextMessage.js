(function(root, factory) {
  root.chatRendererTextMessage = factory(
    root.chatRendererConstants,
    root.chatRendererImgShadow.default,
    root.chatRendererAuthorChip.default,
  )
}(this,
/**
 * @import * as constants from './constants'
 * @import * as ImgShadow from './ImgShadow'
 * @import * as AuthorChip from './AuthorChip'
 * @param {typeof constants} constants
 * @param {typeof ImgShadow.default} ImgShadow
 * @param {typeof AuthorChip.default} AuthorChip
 */
function(constants, ImgShadow, AuthorChip) {
  const exports = {}

  exports.default = {
    template: `
  <lg-live-chat-text-message-renderer :author-type="authorTypeText" :blc-guard-level="privilegeType">
    <div class="liquidGlass-wrapper">
      <div class="liquidGlass-effect"></div>
      <div class="liquidGlass-tint"></div>
      <div class="liquidGlass-shine"></div>
      <div class="liquidGlass-text">
        <img-shadow id="author-photo" height="24" width="24" class="style-scope lg-live-chat-text-message-renderer"
          :imgUrl="avatarUrl"
        ></img-shadow>
        <div id="content" class="style-scope lg-live-chat-text-message-renderer">
          <span id="timestamp" class="style-scope lg-live-chat-text-message-renderer">{{ timeText }}</span>
          <author-chip class="style-scope lg-live-chat-text-message-renderer"
            :isInMemberMessage="false" :authorName="authorName" :authorType="authorType" :privilegeType="privilegeType"
            :medalLevel="medalLevel" :medalName="medalName"
          ></author-chip>
          <span id="message" class="style-scope lg-live-chat-text-message-renderer">
            <template v-for="(content, index) in contentParts">
              <span :key="index" v-if="content.type === CONTENT_PART_TYPE_TEXT">{{ content.text }}</span>
              <!-- 如果CSS设置的尺寸比属性设置的尺寸还大，在图片加载完后布局会变化，可能导致滚动卡住，没什么好的解决方法 -->
              <img :key="index" v-else-if="content.type === CONTENT_PART_TYPE_IMAGE"
                class="emoji lg-formatted-string style-scope lg-live-chat-text-message-renderer"
                :src="content.url" :alt="content.text" :shared-tooltip-text="content.text" :id="\`emoji-\${content.text}\`"
                :width="content.width" :height="content.height"
                :class="{ 'blc-large-emoji': content.height >= 100 }"
              >
            </template>
          </span>
        </div>
      </div>
    </div>
  </lg-live-chat-text-message-renderer>
    `,
    name: 'TextMessage',
    components: {
      ImgShadow,
      AuthorChip
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
      authorTypeText() {
        return constants.AUTHOR_TYPE_TO_TEXT[this.authorType]
      },
    }
  }

  return exports
}))
