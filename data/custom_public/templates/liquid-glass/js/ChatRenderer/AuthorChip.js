(function(root, factory) {
  root.chatRendererAuthorChip = factory(root.chatRendererConstants, root.chatRendererAuthorBadge.default)
}(this,
/**
 * @import * as constants from './constants'
 * @import * as AuthorBadge from './AuthorBadge'
 * @param {typeof constants} constants
 * @param {typeof AuthorBadge.default} AuthorBadge
 */
function(constants, AuthorBadge) {
  const exports = {}

  exports.default = {
    template: `
  <lg-live-chat-author-chip>
    <span id="author-name" dir="auto" class="style-scope lg-live-chat-author-chip" :class="{ member: isInMemberMessage }"
      :type="authorTypeText"
    >
      {{ authorName }}
      <!-- 这里是已验证勋章 -->
      <span id="chip-badges" class="style-scope lg-live-chat-author-chip"></span>
    </span>
    <span v-if="medalName && medalLevel > 0" id="medal" class="style-scope lg-live-chat-author-chip" :data-level="medalLevel">
      <!-- 如果有舰长身份，将舰长徽章显示在粉丝团组件内 -->
      <author-badge v-if="!isInMemberMessage && privilegeType > 0" class="style-scope lg-live-chat-author-chip medal-guard-badge"
        :isAdmin="false" :privilegeType="privilegeType"
      ></author-badge>
      <span class="medal-name">{{ medalName }}</span>
      <span class="medal-level">{{ medalLevel }}</span>
    </span>
    <span id="chat-badges" class="style-scope lg-live-chat-author-chip">
      <author-badge v-if="isInMemberMessage" class="style-scope lg-live-chat-author-chip"
        :isAdmin="false" :privilegeType="privilegeType"
      ></author-badge>
      <template v-else>
        <author-badge v-if="authorType === AUTHOR_TYPE_ADMIN" class="style-scope lg-live-chat-author-chip"
          isAdmin :privilegeType="0"
        ></author-badge>
        <!-- 如果没有粉丝团但有舰长身份，才单独显示舰长徽章 -->
        <author-badge v-if="privilegeType > 0 && (!medalName || medalLevel <= 0)" class="style-scope lg-live-chat-author-chip"
          :isAdmin="false" :privilegeType="privilegeType"
        ></author-badge>
      </template>
    </span>
  </lg-live-chat-author-chip>
    `,
    name: 'AuthorChip',
    components: {
      AuthorBadge
    },
    props: {
      isInMemberMessage: Boolean,
      authorName: String,
      authorType: Number,
      privilegeType: Number,
      medalLevel: Number,
      medalName: String
    },
    data() {
      return {
        AUTHOR_TYPE_ADMIN: constants.AUTHOR_TYPE_ADMIN
      }
    },
    computed: {
      authorTypeText() {
        return constants.AUTHOR_TYPE_TO_TEXT[this.authorType]
      }
    }
  }

  return exports
}))
