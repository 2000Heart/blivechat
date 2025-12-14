(function(root, factory) {
  root.liquidGlassLiquidGlass = factory(
    root.Vue,
    root.liquidGlassGlassContainer,
    root.liquidGlassUtils,
    root.GlassMode
  )
}(this,
/**
 * @import Vue from './vendor/vue.global.prod'
 * @import GlassContainer from './liquid-glass/GlassContainer'
 * @import * as utils from './liquid-glass/utils'
 * @import GlassMode from './liquid-glass/type'
 */
function(Vue, GlassContainerModule, utils, GlassMode) {
  const { defineComponent, ref, watchEffect, computed, onMounted, onUnmounted } = Vue
  const GlassContainer = GlassContainerModule.default
  const { autoPx } = utils

  const LiquidGlass = defineComponent({
    name: 'LiquidGlass',
    components: {
      GlassContainer
    },
    props: {
      displacementScale: {
        type: Number,
        default: 70
      },
      blurAmount: {
        type: Number,
        default: 0.0625
      },
      saturation: {
        type: Number,
        default: 140
      },
      aberrationIntensity: {
        type: Number,
        default: 2
      },
      elasticity: {
        type: Number,
        default: 0.15
      },
      cornerRadius: {
        type: Number,
        default: 999
      },
      padding: {
        type: String,
        default: "24px 32px"
      },
      overLight: {
        type: Boolean,
        default: false
      },
      mode: {
        type: String,
        default: GlassMode.standard
      },
      globalMousePos: Object,
      mouseOffset: Object,
      mouseContainer: Object,
      className: String,
      style: Object,
      onClick: Function,
      effect: {
        type: String,
        default: "liquidGlass"
      }
    },
    setup(props) {
      const glassRef = ref(null)
      const isHovered = ref(false)
      const isActive = ref(false)
      const glassSize = ref({ width: 270, height: 69 })
      const internalGlobalMousePos = ref({ x: 0, y: 0 })
      const internalMouseOffset = ref({ x: 0, y: 0 })

      // Use external mouse position if provided, otherwise use internal
      const globalMousePos = computed(() => props.globalMousePos || internalGlobalMousePos.value)
      const mouseOffset = computed(() => props.mouseOffset || internalMouseOffset.value)

      const handleMouseMove = (e) => {
        const container = props.mouseContainer || (glassRef.value && glassRef.value.$el)
        if (!container) {
          return
        }

        const rect = container.getBoundingClientRect()
        const centerX = rect.left + rect.width / 2
        const centerY = rect.top + rect.height / 2
        Object.assign(internalMouseOffset.value, {
          x: ((e.clientX - centerX) / rect.width) * 100,
          y: ((e.clientY - centerY) / rect.height) * 100,
        })

        Object.assign(internalGlobalMousePos.value, {
          x: e.clientX,
          y: e.clientY,
        })
      }

      // Set up mouse tracking if no external mouse position is provided
      watchEffect((onInvalidate) => {
        if (props.globalMousePos && props.mouseOffset) {
          return
        }

        const container = props.mouseContainer || (glassRef.value && glassRef.value.$el)
        if (!container) {
          return
        }

        container.addEventListener("mousemove", handleMouseMove)

        onInvalidate(() => {
          container.removeEventListener("mousemove", handleMouseMove)
        })
      })

      const calculateDirectionalScale = computed(() => {
        if (!globalMousePos.value.x || !globalMousePos.value.y || !glassRef.value) {
          return "scale(1)"
        }

        const rect = glassRef.value.$el.getBoundingClientRect()
        const pillCenterX = rect.left + rect.width / 2
        const pillCenterY = rect.top + rect.height / 2
        const pillWidth = glassSize.value.width
        const pillHeight = glassSize.value.height

        const deltaX = globalMousePos.value.x - pillCenterX
        const deltaY = globalMousePos.value.y - pillCenterY

        const edgeDistanceX = Math.max(0, Math.abs(deltaX) - pillWidth / 2)
        const edgeDistanceY = Math.max(0, Math.abs(deltaY) - pillHeight / 2)
        const edgeDistance = Math.sqrt(edgeDistanceX * edgeDistanceX + edgeDistanceY * edgeDistanceY)

        const activationZone = 200

        if (edgeDistance > activationZone) {
          return "scale(1)"
        }

        const fadeInFactor = 1 - edgeDistance / activationZone

        const centerDistance = Math.sqrt(deltaX * deltaX + deltaY * deltaY)
        if (centerDistance === 0) {
          return "scale(1)"
        }

        const normalizedX = deltaX / centerDistance
        const normalizedY = deltaY / centerDistance

        const stretchIntensity = Math.min(centerDistance / 300, 1) * props.elasticity * fadeInFactor

        const scaleX = 1 + Math.abs(normalizedX) * stretchIntensity * 0.3 - Math.abs(normalizedY) * stretchIntensity * 0.15
        const scaleY = 1 + Math.abs(normalizedY) * stretchIntensity * 0.3 - Math.abs(normalizedX) * stretchIntensity * 0.15

        return `scaleX(${Math.max(0.8, scaleX)}) scaleY(${Math.max(0.8, scaleY)})`
      })

      const calculateFadeInFactor = computed(() => {
        if (!globalMousePos.value.x || !globalMousePos.value.y || !glassRef.value) {
          return 0
        }

        const rect = glassRef.value.$el.getBoundingClientRect()
        const pillCenterX = rect.left + rect.width / 2
        const pillCenterY = rect.top + rect.height / 2
        const pillWidth = glassSize.value.width
        const pillHeight = glassSize.value.height

        const edgeDistanceX = Math.max(0, Math.abs(globalMousePos.value.x - pillCenterX) - pillWidth / 2)
        const edgeDistanceY = Math.max(0, Math.abs(globalMousePos.value.y - pillCenterY) - pillHeight / 2)
        const edgeDistance = Math.sqrt(edgeDistanceX * edgeDistanceX + edgeDistanceY * edgeDistanceY)

        const activationZone = 200
        return edgeDistance > activationZone ? 0 : 1 - edgeDistance / activationZone
      })

      const calculateElasticTranslation = computed(() => {
        if (!glassRef.value) {
          return { x: 0, y: 0 }
        }

        const fadeInFactor = calculateFadeInFactor.value
        const rect = glassRef.value.$el.getBoundingClientRect()
        const pillCenterX = rect.left + rect.width / 2
        const pillCenterY = rect.top + rect.height / 2

        return {
          x: (globalMousePos.value.x - pillCenterX) * props.elasticity * 0.1 * fadeInFactor,
          y: (globalMousePos.value.y - pillCenterY) * props.elasticity * 0.1 * fadeInFactor,
        }
      })

      // Update glass size whenever component mounts or window resizes
      const updateGlassSize = () => {
        if (glassRef.value && glassRef.value.$el) {
          const rect = glassRef.value.$el.getBoundingClientRect()
          Object.assign(glassSize.value, { width: rect.width, height: rect.height })
        }
      }

      watchEffect((onInvalidate) => {
        updateGlassSize()
        window.addEventListener("resize", updateGlassSize)
        onInvalidate(() => {
          window.removeEventListener("resize", updateGlassSize)
        })
      })

      // 先计算 positionStyles，基于 props.style
      const positionStyles = computed(() => {
        const position = props.style?.position || "relative"
        // 如果 position 是 relative 或者 style 中指定了 position，不使用居中定位
        const shouldUseCentered = position !== "relative" && !props.style?.position && !props.style?.top && !props.style?.left
        return {
          position: position,
          top: shouldUseCentered ? (props.style?.top || "50%") : (props.style?.top || "auto"),
          left: shouldUseCentered ? (props.style?.left || "50%") : (props.style?.left || "auto"),
        }
      })

      const transformStyle = computed(() => {
        const position = props.style?.position || "relative"
        const shouldUseCentered = position !== "relative" && !props.style?.position && !props.style?.top && !props.style?.left
        const translateX = shouldUseCentered ? `calc(-50% + ${calculateElasticTranslation.value.x}px)` : `${calculateElasticTranslation.value.x}px`
        const translateY = shouldUseCentered ? `calc(-50% + ${calculateElasticTranslation.value.y}px)` : `${calculateElasticTranslation.value.y}px`
        return `translate(${translateX}, ${translateY}) ${isActive.value && props.onClick ? "scale(0.96)" : calculateDirectionalScale.value}`
      })

      const baseStyle = computed(() => {
        return {
          ...props.style,
          transform: transformStyle.value,
          transition: "all ease-out 0.2s",
        }
      })

      return {
        glassRef,
        isHovered,
        isActive,
        glassSize,
        mouseOffset,
        baseStyle,
        positionStyles,
        autoPx
      }
    },
    template: `
      <div style="position: relative; display: inline-block; width: fit-content;">
        <div
          :style="{
            ...positionStyles,
            height: glassSize.height,
            width: glassSize.width,
            borderRadius: \`\${cornerRadius}px\`,
            transform: baseStyle.transform,
            transition: baseStyle.transition,
            pointerEvents: 'none',
            background: 'black',
            opacity: overLight ? 0.2 : 0,
          }"></div>
        <div
          :style="{
            ...positionStyles,
            height: glassSize.height,
            width: glassSize.width,
            borderRadius: \`\${cornerRadius}px\`,
            transform: baseStyle.transform,
            transition: baseStyle.transition,
            pointerEvents: 'none',
            background: 'black',
            mixBlendMode: 'overlay',
            opacity: overLight ? 1 : 0,
          }"></div>

        <GlassContainer ref="glassRef" :effect="effect" :style="baseStyle" :cornerRadius="cornerRadius"
          :displacementScale="overLight ? displacementScale * 0.5 : displacementScale" :blurAmount="blurAmount"
          :saturation="saturation" :aberrationIntensity="aberrationIntensity" :glassSize="glassSize" :padding="padding"
          :mouseOffset="mouseOffset" :onMouseEnter="() => isHovered = true" :onMouseLeave="() => isHovered = false"
          :onMouseDown="() => isActive = true" :onMouseUp="() => isActive = false" :active="isActive" :overLight="overLight"
          :onClick="onClick" :mode="mode">
          <slot />
        </GlassContainer>

        <span :style="{
        position: positionStyles.position === 'relative' ? 'absolute' : positionStyles.position,
        top: positionStyles.position === 'relative' ? '0' : positionStyles.top,
        left: positionStyles.position === 'relative' ? '0' : positionStyles.left,
        boxSizing: 'border-box',
        height: autoPx(glassSize.height),
        width: autoPx(glassSize.width),
        borderRadius: \`\${cornerRadius}px\`,
        transform: baseStyle.transform,
        transition: baseStyle.transition,
        pointerEvents: 'none',
        mixBlendMode: 'screen',
        opacity: 0.2,
        padding: '1.5px',
        WebkitMask: 'linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0)',
        WebkitMaskComposite: 'xor',
        maskComposite: 'exclude',
        boxShadow: '0 0 0 0.5px rgba(255, 255, 255, 0.5) inset, 0 1px 3px rgba(255, 255, 255, 0.25) inset, 0 1px 4px rgba(0, 0, 0, 0.35)',
        background: \`linear-gradient( \${135 + mouseOffset.x * 1.2}deg, rgba(255, 255, 255, 0.0) 0%, rgba(255, 255, 255,\${0.12 + Math.abs(mouseOffset.x) * 0.008}) \${Math.max(10, 33 + mouseOffset.y * 0.3)}%, rgba(255, 255, 255, \${0.4 + Math.abs(mouseOffset.x) * 0.012}) \${Math.min(90, 66 + mouseOffset.y * 0.4)}%, rgba(255, 255, 255, 0.0) 100% )\`
        }"></span>

        <span :style="{
        position: positionStyles.position === 'relative' ? 'absolute' : positionStyles.position,
        top: positionStyles.position === 'relative' ? '0' : positionStyles.top,
        left: positionStyles.position === 'relative' ? '0' : positionStyles.left,
        boxSizing: 'border-box',
        height: autoPx(glassSize.height),
        width: autoPx(glassSize.width),
        borderRadius: \`\${cornerRadius}px\`,
        transform: baseStyle.transform,
        transition: baseStyle.transition,
        pointerEvents: 'none',
        mixBlendMode: 'overlay',
        padding: '1.5px',
        WebkitMask: 'linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0)',
        WebkitMaskComposite: 'xor',
        maskComposite: 'exclude',
        boxShadow: '0 0 0 0.5px rgba(255, 255, 255, 0.5) inset, 0 1px 3px rgba(255, 255, 255, 0.25) inset, 0 1px 4px rgba(0, 0, 0, 0.35)',
        background: \`linear-gradient( \${135 + mouseOffset.x * 1.2}deg, rgba(255, 255, 255, 0.0) 0%, rgba(255, 255, 255, \${0.32 + Math.abs(mouseOffset.x) * 0.008}) \${Math.max(10, 33 + mouseOffset.y * 0.3)}%, rgba(255, 255, 255, \${0.6 + Math.abs(mouseOffset.x) * 0.012}) \${Math.min(90, 66 + mouseOffset.y * 0.4)}%, rgba(255, 255, 255, 0.0) 100% )\`
        }"></span>
      </div>
    `
  })

  return { default: LiquidGlass }
}))

