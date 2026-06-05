(function(root, factory) {
  factory(root.Vue, root.blcsdk, root.chatRendererConstants, root.chatRenderer.default)
}(this,
function(Vue, blcsdk, constants, ChatRenderer) {
  const { createApp } = Vue

  const app = createApp({
    components: {
      ChatRenderer,
    },
    data() {
      return {
        config: {
          maxNumber: 60,
          showGiftName: false,
          mergeGift: true,
        }
      }
    },
    async mounted() {
      blcsdk.setMsgHandler(this)
      await blcsdk.init()
      let cfg = blcsdk.getConfig()
      this.config.maxNumber = cfg.maxNumber
      this.config.showGiftName = cfg.showGiftName
      this.config.mergeGift = cfg.mergeGift
    },
    methods: {
      addMsg(msg) {
        this.$refs.renderer.handleMessageGroup([msg])
      },
      delMsgs(ids) {
        let messageGroup = ids.map(
          id => ({
            type: constants.MESSAGE_TYPE_DEL,
            id
          })
        )
        this.$refs.renderer.handleMessageGroup(messageGroup)
      },
      updateMsg(id, newValuesObj) {
        let message = {
          type: constants.MESSAGE_TYPE_UPDATE,
          id,
          newValuesObj
        }
        this.$refs.renderer.handleMessageGroup([message])
      },
    }
  })

  app.config.compilerOptions.isCustomElement = (tag) => tag.startsWith('nc-')

  app.mount('#app')
}))
