(function(root, factory) {
  root.chatRendererMembershipItem = factory(
    root.chatRendererConstants,
    root.chatRendererImgShadow.default,
    root.chatRendererAuthorChip.default,
  )
}(this,
function(constants, ImgShadow, AuthorChip) {
  const exports = {}

  exports.default = {
    template: `
  <nc-live-chat-membership-item-renderer :blc-guard-level="privilegeType">
    <div class="member-header">
      <img-shadow id="author-photo" height="24" width="24"
        :imgUrl="avatarUrl"
      ></img-shadow>
      <author-chip
        :authorName="authorName" :authorType="0" :privilegeType="privilegeType"
        :medalLevel="medalLevel" :medalName="medalName"
      ></author-chip>
      <span v-if="title" id="title">{{ title }}</span>
      <span id="timestamp">{{ timeText }}</span>
    </div>
    <div class="member-message">
      <span class="membership-text">{{ membershipText }}</span>
    </div>
  </nc-live-chat-membership-item-renderer>
    `,
    name: 'MembershipItem',
    components: {
      ImgShadow,
      AuthorChip,
    },
    props: {
      avatarUrl: String,
      authorName: String,
      privilegeType: Number,
      title: String,
      time: Date,
      medalLevel: Number,
      medalName: String
    },
    computed: {
      timeText() {
        return constants.getTimeTextHourMin(this.time)
      },
      membershipText() {
        if (this.privilegeType === 1) {
          return '开通了总督'
        } else if (this.privilegeType === 2) {
          return '开通了提督'
        } else if (this.privilegeType === 3) {
          return '开通了舰长'
        }
        return '开通了会员'
      }
    }
  }

  return exports
}))
