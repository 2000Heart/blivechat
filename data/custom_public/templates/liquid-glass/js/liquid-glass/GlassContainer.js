(function(root, factory) {
  root.liquidGlassGlassContainer = factory(
    root.Vue,
    root.liquidGlassGlassFilter,
    root.ShaderDisplacementGenerator,
    root.liquidGlassUtils,
    root.GlassMode
  )
}(this,
/**
 * @import Vue from './vendor/vue.global.prod'
 * @import GlassFilter from './liquid-glass/GlassFilter'
 * @import ShaderDisplacementGenerator from './liquid-glass/shader-util'
 * @import * as utils from './liquid-glass/utils'
 * @import GlassMode from './liquid-glass/type'
 */
function(Vue, GlassFilterModule, ShaderDisplacementGenerator, utils, GlassMode) {
  const { defineComponent, ref, watch, computed } = Vue
  const GlassFilter = GlassFilterModule.default
  const { uuid } = utils

  const GlassContainer = defineComponent({
    name: 'GlassContainer',
    components: {
      GlassFilter
    },
    props: {
      className: {
        type: String,
        default: ""
      },
      style: Object,
      displacementScale: {
        type: Number,
        default: 25
      },
      blurAmount: {
        type: Number,
        default: 12
      },
      saturation: {
        type: Number,
        default: 180
      },
      aberrationIntensity: {
        type: Number,
        default: 2
      },
      mouseOffset: Object,
      onMouseLeave: Function,
      onMouseEnter: Function,
      onMouseDown: Function,
      onMouseUp: Function,
      active: {
        type: Boolean,
        default: false
      },
      overLight: {
        type: Boolean,
        default: false
      },
      cornerRadius: {
        type: Number,
        default: 999
      },
      padding: {
        type: String,
        default: "24px 32px"
      },
      glassSize: {
        type: Object,
        default: () => ({ width: 270, height: 69 })
      },
      mode: {
        type: String,
        default: GlassMode.standard
      },
      effect: {
        type: String,
        default: "liquidGlass"
      },
      onClick: Function
    },
    setup(props) {
      const shaderMapUrl = ref("")
      const isFirefox = window.navigator.userAgent.toLowerCase().includes("firefox")
      const filterId = uuid()

      // Generate shader-based displacement map using shaderUtils
      const generateShaderDisplacementMap = async (width, height) => {
        const generator = new ShaderDisplacementGenerator({
          width,
          height,
          effect: props.effect,
        })

        const dataUrl = await generator.updateShader()
        generator.destroy()

        return dataUrl
      }

      watch(() => [props.mode, props.glassSize.width, props.glassSize.height, props.effect], async () => {
        if (props.mode === GlassMode.shader) {
          const url = await generateShaderDisplacementMap(props.glassSize.width, props.glassSize.height)
          shaderMapUrl.value = url
        }
      }, { immediate: true })

      const backdropStyle = computed(() => {
        return {
          filter: isFirefox ? undefined : `url(#${filterId})`,
          backdropFilter: `blur(${(props.overLight ? 12 : 4) + props.blurAmount * 32}px) saturate(${props.saturation}%)`,
        }
      })

      return {
        shaderMapUrl,
        filterId,
        backdropStyle
      }
    },
    template: `
      <div :class="\`relative \${className} \${active ? 'active' : ''} \${onClick ? 'cursor-pointer' : ''}\`"
        :style="style" @click="onClick">
        <GlassFilter :mode="mode" :id="filterId" :displacementScale="displacementScale"
          :aberrationIntensity="aberrationIntensity" :width="glassSize.width" :height="glassSize.height"
          :shaderMapUrl="shaderMapUrl" />

        <div class="glass" :style="{
          borderRadius: \`\${cornerRadius}px\`,
          position: 'relative',
          display: 'inline-flex',
          alignItems: 'center',
          gap: '24px',
          padding: padding,
          overflow: 'hidden',
          transition: 'all 0.2s ease-in-out',
          boxShadow: overLight ? '0px 16px 70px rgba(0, 0, 0, 0.75)' : '0px 12px 40px rgba(0, 0, 0, 0.25)',
        }" @mouseenter="onMouseEnter" @mouseleave="onMouseLeave" @mousedown="onMouseDown" @mouseup="onMouseUp">
          <span class="glass__warp" :style="{
            ...backdropStyle,
            position: 'absolute',
            inset: '0',
          }"></span>

          <div class="transition-all duration-150 ease-in-out text-white" :style="{
            position: 'relative',
            zIndex: 1,
            font: '500 20px/1 system-ui',
            textShadow: overLight ? '0px 2px 12px rgba(0, 0, 0, 0)' : '0px 2px 12px rgba(0, 0, 0, 0.4)',
          }">
            <slot />
          </div>
        </div>
      </div>
    `
  })

  return { default: GlassContainer }
}))

