(function(root, factory) {
  root.chatRendererAuthorChip = factory(root.chatRendererConstants, root.chatRendererAuthorBadge.default)
}(this,
function(constants, AuthorBadge) {
  const exports = {}

  exports.default = {
    template: `
  <nc-live-chat-author-chip>
    <span id="author-name" dir="auto" class="style-scope nc-live-chat-author-chip"
      :type="authorTypeText"
    >
      {{ authorName }}
    </span>
    <span v-if="medalName && medalLevel > 0" id="medal" class="style-scope nc-live-chat-author-chip" :data-level="medalLevel">
      <author-badge v-if="privilegeType > 0" class="medal-guard-badge style-scope nc-live-chat-author-chip"
        :isAdmin="false" :privilegeType="privilegeType"
      ></author-badge>
      <span class="medal-name">{{ medalName }}</span>
      <span class="medal-level">{{ medalLevel }}</span>
    </span>
    <span id="chat-badges" class="style-scope nc-live-chat-author-chip">
      <author-badge v-if="authorType === AUTHOR_TYPE_ADMIN && (!medalName || medalLevel <= 0)"
        isAdmin :privilegeType="0"
      ></author-badge>
      <author-badge v-if="privilegeType > 0 && (!medalName || medalLevel <= 0)"
        :isAdmin="false" :privilegeType="privilegeType"
      ></author-badge>
    </span>
  </nc-live-chat-author-chip>
    `,
    name: 'AuthorChip',
    components: {
      AuthorBadge
    },
    props: {
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
