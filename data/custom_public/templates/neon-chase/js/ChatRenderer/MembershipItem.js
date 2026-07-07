(function(root, factory) {
  root.chatRendererMembershipItem = factory()
}(this,
function() {
  const exports = {}

  // ===== 三档配置 =====
  const TIERS = {
    3: { // 舰长
      name: '舰长',
      bgGradient: 'radial-gradient(ellipse at 50% 50%, rgba(33,150,243,0.05) 0%, transparent 60%)',
      avatarBorder: '2.5px solid rgba(33,150,243,0.6)',
      avatarShadow: '0 0 40px rgba(33,150,243,0.3), 0 0 80px rgba(33,150,243,0.1)',
      textColor: '#B3E5FC',
      textShadow: '0 0 15px rgba(33,150,243,0.5), 0 0 30px rgba(33,150,243,0.2)',
      coronaColors: [
        'radial-gradient(ellipse, rgba(33,150,243,0.25) 0%, rgba(33,150,243,0.08) 40%, transparent 70%)',
        'radial-gradient(ellipse, rgba(33,150,243,0.12) 0%, rgba(33,150,243,0.04) 40%, transparent 70%)',
        'radial-gradient(ellipse, rgba(33,150,243,0.06) 0%, transparent 65%)',
      ],
      coronaSizes: [80, 110, 150],
      coronaAnims: ['corona-pulse 2.5s ease-in-out infinite', 'corona-pulse 2.5s ease-in-out infinite 0.4s', 'corona-pulse2 3s ease-in-out infinite 0.8s'],
      rings: [
        { size: 200, border: '1px solid rgba(33,150,243,0.08)' },
        { size: 140, border: '1px dashed rgba(33,150,243,0.05)' },
      ],
      planets: [
        { orbitSize: 200, speed: '14s', rev: false, pSize: 14, pBg: 'radial-gradient(circle at 35% 35%, #4FC3F7, #0D47A1)', pShadow: '0 0 20px rgba(79,195,247,0.6), 0 0 40px rgba(79,195,247,0.2)' },
        { orbitSize: 140, speed: '10s', rev: true, pSize: 10, pBg: 'radial-gradient(circle at 35% 35%, #00E5FF, #006064)', pShadow: '0 0 16px rgba(0,229,255,0.5), 0 0 30px rgba(0,229,255,0.15)' },
      ],
      particleCount: 4,
      meteorCount: 3,
      starCount: 7,
      hasOrbitPulse: false,
      hasShimmer: false,
      hasSupernova: false,
      hasCorePulse: false,
      orbitPulseAnim: '',
    },
    2: { // 提督
      name: '提督',
      bgGradient: 'radial-gradient(ellipse at 50% 50%, rgba(156,39,176,0.06) 0%, transparent 60%)',
      avatarBorder: '2.5px solid rgba(156,39,176,0.6)',
      avatarShadow: '0 0 40px rgba(156,39,176,0.3), 0 0 80px rgba(156,39,176,0.1)',
      textColor: '#E1BEE7',
      textShadow: '0 0 15px rgba(156,39,176,0.5), 0 0 30px rgba(156,39,176,0.2)',
      coronaColors: [
        'radial-gradient(ellipse, rgba(156,39,176,0.25) 0%, rgba(156,39,176,0.08) 40%, transparent 70%)',
        'radial-gradient(ellipse, rgba(156,39,176,0.12) 0%, rgba(156,39,176,0.04) 40%, transparent 70%)',
        'radial-gradient(ellipse, rgba(156,39,176,0.06) 0%, transparent 65%)',
      ],
      coronaSizes: [80, 110, 150],
      coronaAnims: ['corona-pulse 2.5s ease-in-out infinite', 'corona-pulse 2.5s ease-in-out infinite 0.4s', 'corona-pulse2 3s ease-in-out infinite 0.8s'],
      rings: [
        { size: 220, border: '1px solid rgba(156,39,176,0.1)', pulse: true },
        { size: 165, border: '1px dashed rgba(156,39,176,0.07)' },
        { size: 110, border: '1px solid rgba(156,39,176,0.05)' },
      ],
      planets: [
        { orbitSize: 220, speed: '18s', rev: false, pSize: 16, pBg: 'radial-gradient(circle at 35% 35%, #CE93D8, #4A148C)', pShadow: '0 0 24px rgba(206,147,216,0.6), 0 0 45px rgba(206,147,216,0.2)' },
        { orbitSize: 165, speed: '13s', rev: true, pSize: 12, pBg: 'radial-gradient(circle at 35% 35%, #EA80FC, #6A1B9A)', pShadow: '0 0 18px rgba(234,128,252,0.5), 0 0 35px rgba(234,128,252,0.15)' },
        { orbitSize: 110, speed: '8s', rev: false, pSize: 8, pBg: 'radial-gradient(circle at 35% 35%, #F48FB1, #880E4F)', pShadow: '0 0 14px rgba(244,143,177,0.5)' },
      ],
      particleCount: 6,
      meteorCount: 4,
      starCount: 9,
      hasOrbitPulse: true,
      hasShimmer: false,
      hasSupernova: false,
      hasCorePulse: false,
      orbitPulseAnim: 'orbit-energy-purple 3s ease-in-out infinite, orbit-spin 20s linear infinite',
    },
    1: { // 总督
      name: '总督',
      bgGradient: 'radial-gradient(ellipse at 50% 50%, rgba(255,215,0,0.08) 0%, rgba(230,81,0,0.03) 30%, transparent 65%)',
      avatarBorder: '2.5px solid rgba(255,215,0,0.7)',
      avatarShadow: '0 0 45px rgba(255,215,0,0.4), 0 0 90px rgba(255,215,0,0.15)',
      textColor: '#FFD700',
      textShadow: '',
      coronaColors: [
        'radial-gradient(ellipse, rgba(255,215,0,0.3) 0%, rgba(255,215,0,0.1) 40%, transparent 70%)',
        'radial-gradient(ellipse, rgba(255,215,0,0.15) 0%, rgba(255,179,0,0.05) 40%, transparent 70%)',
        'radial-gradient(ellipse, rgba(255,215,0,0.08) 0%, rgba(230,81,0,0.03) 40%, transparent 65%)',
      ],
      coronaSizes: [80, 115, 160],
      coronaAnims: ['corona-pulse 2s ease-in-out infinite', 'corona-pulse 2s ease-in-out infinite 0.35s', 'corona-pulse2 2.8s ease-in-out infinite 0.7s'],
      rings: [
        { size: 240, border: '1.5px solid rgba(255,215,0,0.1)', pulse: true },
        { size: 190, border: '1px dashed rgba(255,215,0,0.07)' },
        { size: 140, border: '1px solid rgba(255,215,0,0.05)' },
        { size: 85, border: '1px dashed rgba(255,215,0,0.04)' },
      ],
      planets: [
        { orbitSize: 240, speed: '22s', rev: false, pSize: 18, pBg: 'radial-gradient(circle at 35% 35%, #FFD700, #BF360C)', pShadow: '0 0 28px rgba(255,215,0,0.7), 0 0 50px rgba(255,215,0,0.25)' },
        { orbitSize: 190, speed: '16s', rev: true, pSize: 14, pBg: 'radial-gradient(circle at 35% 35%, #FFB300, #E65100)', pShadow: '0 0 22px rgba(255,179,0,0.6), 0 0 40px rgba(255,179,0,0.2)' },
        { orbitSize: 140, speed: '11s', rev: false, pSize: 11, pBg: 'radial-gradient(circle at 35% 35%, #FFF8E1, #FF6F00)', pShadow: '0 0 18px rgba(255,248,225,0.5), 0 0 35px rgba(255,111,0,0.15)' },
        { orbitSize: 85, speed: '6s', rev: true, pSize: 7, pBg: 'radial-gradient(circle at 35% 35%, #fff, #FFD700)', pShadow: '0 0 20px rgba(255,215,0,0.8), 0 0 40px rgba(255,215,0,0.3)' },
      ],
      particleCount: 10,
      meteorCount: 5,
      starCount: 12,
      hasOrbitPulse: true,
      hasShimmer: true,
      hasSupernova: true,
      hasCorePulse: true,
      orbitPulseAnim: 'orbit-energy 3s ease-in-out infinite, orbit-spin 22s linear infinite',
    },
  }

  // ===== 粒子配置生成 =====
  function generateParticleConfigs(count, baseColor, glowColor) {
    const positions = [
      { top: '3%', left: '8%' }, { top: '85%', left: '88%' },
      { top: '12%', left: '78%' }, { top: '72%', left: '5%' },
      { top: '6%', left: '42%' }, { top: '92%', left: '45%' },
      { top: '62%', left: '93%' }, { top: '25%', left: '28%' },
      { top: '52%', left: '58%' }, { top: '32%', left: '72%' },
    ]
    const anims = ['float1', 'float2']
    const delays = ['0s', '0.5s', '1s', '1.5s', '2s', '2.5s', '3s', '3.5s', '4s', '4.5s']
    const sizes = [3, 2.5, 3, 2.5, 3.5, 2, 3, 1.5, 1.5, 1.5]
    const configs = []
    for (let i = 0; i < count; i++) {
      const pos = positions[i % positions.length]
      configs.push({
        size: sizes[i % sizes.length],
        bg: baseColor,
        shadow: glowColor ? `0 0 ${6 + (i % 3) * 2}px ${glowColor}` : 'none',
        top: pos.top,
        left: pos.left,
        anim: `${anims[i % 2]} ${3 + (i % 3)}s infinite ${delays[i % delays.length]}`,
      })
    }
    return configs
  }

  // ===== 流星配置生成 =====
  function generateMeteorConfigs(count, color, opacity) {
    const positions = [
      { top: '10%', left: '88%', speed: '3.5s', delay: '3s', rev: false, width: 12, height: 3 },
      { top: '65%', left: '4%', speed: '4s', delay: '6s', rev: true, width: 10, height: 2.5 },
      { top: '45%', left: '92%', speed: '3s', delay: '8s', rev: false, width: 8, height: 2 },
      { top: '5%', left: '90%', speed: '3s', delay: '2s', rev: false, width: 11, height: 2.5 },
      { top: '30%', left: '95%', speed: '4s', delay: '7s', rev: false, width: 9, height: 2 },
    ]
    const configs = []
    for (let i = 0; i < count; i++) {
      const p = positions[i % positions.length]
      configs.push({
        width: p.width,
        height: p.height,
        bg: `linear-gradient(90deg, rgba(${color},${opacity - i * 0.05}), transparent)`,
        shadow: `0 0 ${12 + i * 3}px rgba(${color},${0.3 + i * 0.05})`,
        top: p.top,
        left: p.left,
        anim: p.rev
          ? `meteor-shoot-rev ${p.speed} linear infinite ${p.delay}`
          : `meteor-shoot ${p.speed} linear infinite ${p.delay}`,
      })
    }
    return configs
  }

  // ===== 星星配置生成 =====
  function generateStarConfigs(count) {
    const positions = [
      { top: '5%', left: '8%' }, { top: '12%', left: '85%' },
      { top: '20%', left: '92%' }, { top: '82%', left: '3%' },
      { top: '90%', left: '95%' }, { top: '3%', left: '45%' },
      { top: '92%', left: '50%' }, { top: '48%', left: '2%' },
      { top: '62%', left: '97%' }, { top: '35%', left: '96%' },
      { top: '75%', left: '98%' }, { top: '15%', left: '3%' },
    ]
    const twinkles = ['twinkle1', 'twinkle2', 'twinkle3']
    const configs = []
    for (let i = 0; i < count; i++) {
      const p = positions[i % positions.length]
      configs.push({
        size: i % 3 === 0 ? 2.5 : (i % 3 === 1 ? 2 : 1.5),
        top: p.top,
        left: p.left,
        anim: `${twinkles[i % 3]} ${1.8 + (i % 5) * 0.4}s ease-in-out ${(i % 4) * 0.5}s infinite`,
      })
    }
    return configs
  }

  // ===== 超新星粒子配置 =====
  function generateSupernovaConfigs() {
    return [
      { size: 4, bg: '#FFD700', shadow: '0 0 20px #FFD700', tx: -80, ty: -60, delay: '0.1s' },
      { size: 3, bg: '#FFE082', shadow: '0 0 15px #FFE082', tx: 70, ty: -50, delay: '0.2s' },
      { size: 4, bg: '#FFD700', shadow: '0 0 20px #FFD700', tx: -60, ty: 70, delay: '0.15s' },
      { size: 3, bg: '#fff', shadow: '0 0 25px #FFD700', tx: 85, ty: 55, delay: '0.25s' },
      { size: 3.5, bg: '#FFE082', shadow: '0 0 18px #FFE082', tx: -90, ty: 30, delay: '0.3s' },
      { size: 2.5, bg: '#fff', shadow: '0 0 15px #FFD700', tx: 45, ty: -80, delay: '0.35s' },
      { size: 3, bg: '#FFD700', shadow: '0 0 18px #FFD700', tx: -40, ty: -85, delay: '0.4s' },
      { size: 4, bg: '#E65100', shadow: '0 0 20px #E65100', tx: 60, ty: 75, delay: '0.12s' },
    ]
  }

  const PARTICLE_COLORS = {
    3: { bg: '#90CAF9', glow: '#90CAF9' },
    2: { bg: '#CE93D8', glow: '#CE93D8' },
    1: { bg: '#FFE082', glow: '#FFE082' },
  }

  const METEOR_COLORS = {
    3: { rgb: '79,195,247' },
    2: { rgb: '206,147,216' },
    1: { rgb: '255,215,0' },
  }

  exports.default = {
    template: `
  <nc-live-chat-membership-item-renderer>
    <!-- 星云背景 -->
    <div class="nebula-bg" :style="{ background: tier.bgGradient }"></div>

    <!-- 核心脉冲（总督） -->
    <div v-if="tier.hasCorePulse" class="core-pulse"></div>

    <!-- 日冕光晕 -->
    <div v-for="(c, i) in coronaLayers" :key="'c'+i" class="corona-layer"
      :style="c.style"
    ></div>

    <!-- 轨道装饰环 -->
    <div v-for="(r, i) in ringStyles" :key="'r'+i" class="orbit-deco"
      :style="r.style"
    ></div>

    <!-- 行星公转 -->
    <div v-for="(p, i) in planetStyles" :key="'p'+i"
      :class="['orbit-path', p.cls]"
      :style="p.style"
    >
      <div class="planet" :style="p.planetStyle"></div>
    </div>

    <!-- 头像 -->
    <div class="member-avatar" :style="avatarStyle">
      <img :src="avatarUrl" alt="">
    </div>

    <!-- 文字 -->
    <div :class="['member-text', { 'shimmer-text': tier.hasShimmer }]" :style="textStyle">
      {{ authorName }}开通了{{ tier.name }}
    </div>
  </nc-live-chat-membership-item-renderer>
    `,
    name: 'MembershipItem',
    props: {
      avatarUrl: String,
      authorName: String,
      privilegeType: Number,
      title: String,
      time: Date,
      medalLevel: Number,
      medalName: String,
    },
    computed: {
      tier() {
        return TIERS[this.privilegeType] || TIERS[3]
      },
      coronaLayers() {
        return this.tier.coronaSizes.map((size, i) => ({
          style: {
            width: size + 'px',
            height: size + 'px',
            background: this.tier.coronaColors[i],
            animation: this.tier.coronaAnims[i],
          }
        }))
      },
      ringStyles() {
        return this.tier.rings.map(r => {
          const half = r.size / 2
          const base = {
            width: r.size + 'px',
            height: r.size + 'px',
            margin: -half + 'px 0 0 ' + -half + 'px',
            border: r.border,
          }
          if (r.pulse && this.tier.hasOrbitPulse) {
            base.animation = this.tier.orbitPulseAnim
          }
          return base
        })
      },
      planetStyles() {
        return this.tier.planets.map(p => {
          const half = p.orbitSize / 2
          return {
            style: {
              width: p.orbitSize + 'px',
              height: p.orbitSize + 'px',
              margin: -half + 'px 0 0 ' + -half + 'px',
              '--speed': p.speed,
            },
            cls: p.rev ? 'orbit-rev' : 'orbit-fwd',
            planetStyle: {
              width: p.pSize + 'px',
              height: p.pSize + 'px',
              background: p.pBg,
              boxShadow: p.pShadow,
            }
          }
        })
      },
      avatarStyle() {
        return {
          border: this.tier.avatarBorder,
          boxShadow: this.tier.avatarShadow,
        }
      },
      textStyle() {
        if (this.tier.hasShimmer) return {}
        return {
          color: this.tier.textColor,
          textShadow: this.tier.textShadow,
        }
      },
    },
    mounted() {
      const el = this.$el

      // 用 Web Animations API 播放入场动画，替代 CSS animation
      // WAAPI 动画不受 CSS style recalc / compositor layer 重建影响
      if (el) {
        el.style.opacity = '0'
        el.style.transform = 'scale(0.3)'
        const anim = el.animate([
          { transform: 'scale(0.3)', opacity: '0' },
          { transform: 'scale(1.08)', opacity: '1', offset: 0.25 },
          { transform: 'scale(0.95)', offset: 0.45 },
          { transform: 'scale(1.02)', offset: 0.65 },
          { transform: 'scale(1)', opacity: '1' }
        ], {
          duration: 2500,
          easing: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
          fill: 'forwards'
        })
        anim.onfinish = () => {
          el.style.transform = 'scale(1)'
          el.style.opacity = '1'
        }
      }

      this.$nextTick(() => {
        if (!el) return

        // 生成闪烁星星
        const starCfgs = generateStarConfigs(this.tier.starCount)
        starCfgs.forEach(cfg => {
          const div = document.createElement('div')
          div.className = 'star'
          div.style.cssText = `width:${cfg.size}px;height:${cfg.size}px;background:#fff;top:${cfg.top};left:${cfg.left};animation:${cfg.anim}`
          el.appendChild(div)
        })

        // 生成漂浮粒子
        const pc = PARTICLE_COLORS[this.privilegeType] || PARTICLE_COLORS[3]
        const particleCfgs = generateParticleConfigs(this.tier.particleCount, pc.bg, pc.glow)
        particleCfgs.forEach(cfg => {
          const div = document.createElement('div')
          div.className = 'particle'
          div.style.cssText = `width:${cfg.size}px;height:${cfg.size}px;background:${cfg.bg};box-shadow:${cfg.shadow};top:${cfg.top};left:${cfg.left};animation:${cfg.anim}`
          el.appendChild(div)
        })

        // 生成流星
        const mc = METEOR_COLORS[this.privilegeType] || METEOR_COLORS[3]
        const meteorCfgs = generateMeteorConfigs(this.tier.meteorCount, mc.rgb, 0.8)
        meteorCfgs.forEach(cfg => {
          const div = document.createElement('div')
          div.className = 'meteor'
          div.style.cssText = `width:${cfg.width}px;height:${cfg.height}px;background:${cfg.bg};box-shadow:${cfg.shadow};top:${cfg.top};left:${cfg.left};animation:${cfg.anim}`
          el.appendChild(div)
        })

        // 超新星爆发（总督）
        if (this.tier.hasSupernova) {
          const novaCfgs = generateSupernovaConfigs()
          novaCfgs.forEach(cfg => {
            const div = document.createElement('div')
            div.className = 'supernova-particle'
            div.style.cssText = `width:${cfg.size}px;height:${cfg.size}px;background:${cfg.bg};box-shadow:${cfg.shadow};--tx:${cfg.tx}px;--ty:${cfg.ty}px;animation:supernova-burst 2.5s ease-out forwards;animation-delay:${cfg.delay}`
            el.appendChild(div)
          })
        }
      })
    },
  }

  return exports
}))
