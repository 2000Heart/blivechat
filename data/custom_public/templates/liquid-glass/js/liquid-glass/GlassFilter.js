(function(root, factory) {
  root.liquidGlassGlassFilter = factory(
    root.Vue,
    root.liquidGlassUtils,
    root.GlassMode
  )
}(this,
/**
 * @import Vue from './vendor/vue.global.prod'
 * @import * as utils from './liquid-glass/utils'
 * @import GlassMode from './liquid-glass/type'
 */
function(Vue, utils, GlassMode) {
  const { defineComponent, computed } = Vue
  const { autoPx, displacementMap, polarDisplacementMap, prominentDisplacementMap } = utils

  function getMap(mode, shaderMapUrl) {
    switch (mode) {
      case GlassMode.standard:
        return displacementMap
      case GlassMode.polar:
        return polarDisplacementMap
      case GlassMode.prominent:
        return prominentDisplacementMap
      case GlassMode.shader:
        return shaderMapUrl || displacementMap
      default:
        throw new Error(`Invalid mode: ${mode}`)
    }
  }

  const GlassFilter = defineComponent({
    name: 'GlassFilter',
    props: {
      id: String,
      displacementScale: Number,
      aberrationIntensity: Number,
      width: [Number, String],
      height: [Number, String],
      mode: String,
      shaderMapUrl: String
    },
    setup(props) {
      const customFilterStyle = computed(() => {
        return {
          position: 'absolute',
          width: autoPx(props.width),
          height: autoPx(props.height),
        }
      })

      const scale = computed(() => {
        return props.mode === GlassMode.shader ? 1 : -1
      })

      const offset = computed(() => {
        return `${Math.max(30, 80 - props.aberrationIntensity * 2)}%`
      })

      return {
        customFilterStyle,
        scale,
        offset,
        getMap
      }
    },
    template: `
      <svg :style="customFilterStyle" aria-hidden="true">
        <defs>
          <radialGradient :id="\`\${id}-edge-mask\`" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="black" stopOpacity="0" />
            <stop :offset="offset" stopColor="black" stopOpacity="0" />
            <stop offset="100%" stopColor="white" stopOpacity="1" />
          </radialGradient>
          <filter :id="id" x="-35%" y="-35%" width="170%" height="170%" colorInterpolationFilters="sRGB">
            <feImage id="feimage" x="0" y="0" width="100%" height="100%" result="DISPLACEMENT_MAP"
              :href="getMap(mode, shaderMapUrl)" preserveAspectRatio="xMidYMid slice" />

            <!--
              关键修复点：
              你的玻璃材质本身是“半透明渐变”，直接用 SourceAlpha 做边缘环会把渐变的 alpha 变化也当成“边缘”，
              于是内部会出现一块更深的“模糊/脏影”，甚至看起来像“整块都糊”。
              这里先把 SourceGraphic 的 A 通道强制设为 1（仅保留形状，忽略渐变 alpha），再做 erode/out 得到纯边缘环。
            -->
            <feColorMatrix in="SourceGraphic" type="matrix" values="1 0 0 0 0
              0 1 0 0 0
              0 0 1 0 0
              0 0 0 0 1" result="SOURCE_SOLID_ALPHA" />
            <feMorphology in="SOURCE_SOLID_ALPHA" operator="erode"
              :radius="Math.max(1, Math.min(6, Math.round(1 + aberrationIntensity * 0.8)))"
              result="ALPHA_ERODED" />
            <feComposite in="SOURCE_SOLID_ALPHA" in2="ALPHA_ERODED" operator="out" result="EDGE_MASK" />

            <feOffset in="SourceGraphic" dx="0" dy="0" result="CENTER_ORIGINAL" />

            <feDisplacementMap in="SourceGraphic" in2="DISPLACEMENT_MAP" :scale="displacementScale * scale"
              xChannelSelector="R" yChannelSelector="B" result="RED_DISPLACED" />
            <feColorMatrix in="RED_DISPLACED" type="matrix" values="1 0 0 0 0
              0 0 0 0 0
              0 0 0 0 0
              0 0 0 1 0" result="RED_CHANNEL" />

            <feDisplacementMap in="SourceGraphic" in2="DISPLACEMENT_MAP"
              :scale="displacementScale * (scale - aberrationIntensity * 0.05)" xChannelSelector="R"
              yChannelSelector="B" result="GREEN_DISPLACED" />
            <feColorMatrix in="GREEN_DISPLACED" type="matrix" values="0 0 0 0 0
              0 1 0 0 0
              0 0 0 0 0
              0 0 0 1 0" result="GREEN_CHANNEL" />

            <feDisplacementMap in="SourceGraphic" in2="DISPLACEMENT_MAP"
              :scale="displacementScale * (scale - aberrationIntensity * 0.1)" xChannelSelector="R"
              yChannelSelector="B" result="BLUE_DISPLACED" />
            <feColorMatrix in="BLUE_DISPLACED" type="matrix" values="0 0 0 0 0
              0 0 0 0 0
              0 0 1 0 0
              0 0 0 1 0" result="BLUE_CHANNEL" />

            <feBlend in="GREEN_CHANNEL" in2="BLUE_CHANNEL" mode="screen" result="GB_COMBINED" />
            <feBlend in="RED_CHANNEL" in2="GB_COMBINED" mode="screen" result="RGB_COMBINED" />

            <feGaussianBlur in="RGB_COMBINED" :stdDeviation="Math.max(0.1, 0.5 - aberrationIntensity * 0.1)"
              result="ABERRATED_BLURRED" />

            <feComposite in="ABERRATED_BLURRED" in2="EDGE_MASK" operator="in" result="EDGE_ABERRATION" />

            <feComponentTransfer in="EDGE_MASK" result="INVERTED_MASK">
              <feFuncA type="table" tableValues="1 0" />
            </feComponentTransfer>
            <feComposite in="CENTER_ORIGINAL" in2="INVERTED_MASK" operator="in" result="CENTER_CLEAN" />

            <feComposite in="EDGE_ABERRATION" in2="CENTER_CLEAN" operator="over" />
          </filter>
        </defs>
      </svg>
    `
  })

  return { default: GlassFilter }
}))

