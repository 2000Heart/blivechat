(function(root, factory) {
  root.chatRendererMembershipItem = factory(
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
  <lg-live-chat-membership-item-renderer class="style-scope lg-live-chat-item-list-renderer"
    :blc-guard-level="privilegeType"
  >
    <div class="liquidGlass-wrapper">
      <div class="liquidGlass-effect"></div>
      <div class="liquidGlass-tint"></div>
      <div class="liquidGlass-shine"></div>
      <div class="liquidGlass-text">
        <div class="member-decoration"></div>
        <div class="member-header">
          <img-shadow id="author-photo" height="24" width="24" class="style-scope lg-live-chat-membership-item-renderer"
            :imgUrl="avatarUrl"
          ></img-shadow>
          <author-chip class="style-scope lg-live-chat-membership-item-renderer"
            isInMemberMessage :authorName="authorName" :authorType="0" :privilegeType="privilegeType"
          ></author-chip>
          <span v-if="title" id="title" class="style-scope lg-live-chat-membership-item-renderer">{{ title }}</span>
          <span id="timestamp" class="style-scope lg-live-chat-membership-item-renderer">{{ timeText }}</span>
        </div>
        <div class="member-message">
          <span class="membership-text">{{ membershipText }}</span>
        </div>
      </div>
    </div>
  </lg-live-chat-membership-item-renderer>
    `,
    name: 'MembershipItem',
    components: {
      ImgShadow,
      AuthorChip
    },
    props: {
      avatarUrl: String,
      authorName: String,
      privilegeType: Number,
      title: String,
      time: Date
    },
    computed: {
      timeText() {
        return constants.getTimeTextHourMin(this.time)
      },
      membershipText() {
        // 根据舰长等级生成不同的开通文案
        // level 1 = 总督, level 2 = 提督, level 3 = 舰长
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
