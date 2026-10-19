<template>
  <span v-if="badges.length > 0" class="identity-badges">
    <span
      v-for="(badge, index) in badges"
      :key="`${badge.type}-${index}`"
      class="identity-badge"
      :class="badge.classNames"
    >
      {{ badge.text }}
    </span>
  </span>
</template>

<script>
import * as constants from './constants'

function pickObject(...values) {
  for (const value of values) {
    if (value && typeof value === 'object') {
      return value
    }
  }
  return {}
}

function pickString(...values) {
  for (const value of values) {
    if (typeof value === 'string') {
      const text = value.trim()
      if (text !== '') {
        return text
      }
    }
  }
  return ''
}

function pickNumber(...values) {
  for (const value of values) {
    const num = Number(value)
    if (Number.isFinite(num) && num > 0) {
      return Math.floor(num)
    }
  }
  return 0
}

export default {
  name: 'IdentityBadges',
  props: {
    platform: {
      type: String,
      default: ''
    },
    platformMeta: {
      type: Object,
      default: () => ({})
    },
    fanIdentity: {
      type: Object,
      default: () => ({})
    },
    privilegeType: {
      type: Number,
      default: 0
    },
    medalName: {
      type: String,
      default: ''
    },
    medalLevel: {
      type: Number,
      default: 0
    },
    messageExt: {
      type: Object,
      default: () => ({})
    }
  },
  computed: {
    normalizedPlatform() {
      const ext = this.messageExt || {}
      const meta = this.platformMeta || {}
      return pickString(
        this.platform,
        meta.platform,
        ext.platform,
        ext.platform_name,
        ext.unifiedPlatform
      ).toLowerCase()
    },
    normalizedPlatformMeta() {
      const ext = this.messageExt || {}
      return pickObject(
        this.platformMeta,
        ext.platform_meta,
        ext.platformMeta,
        ext.unified_platform_meta,
        ext.unifiedPlatformMeta,
        ext.extra && ext.extra.platform_meta,
        ext.extra && ext.extra.platformMeta
      )
    },
    normalizedFanIdentity() {
      const ext = this.messageExt || {}
      return pickObject(
        this.fanIdentity,
        ext.fan_identity,
        ext.fanIdentity,
        ext.unified_fan_identity,
        ext.unifiedFanIdentity,
        ext.extra && ext.extra.fan_identity,
        ext.extra && ext.extra.fanIdentity
      )
    },
    badges() {
      if (this.normalizedPlatform === 'bilibili') {
        return this.bilibiliBadges
      }
      if (this.normalizedPlatform === 'douyin') {
        return this.douyinBadges
      }
      return []
    },
    bilibiliBadges() {
      const badgeList = []
      if (this.privilegeType > 0) {
        const guardText = constants.getShowGuardLevelText(this.privilegeType)
        if (guardText) {
          badgeList.push(this.buildBadge('guard', guardText, 'bili'))
        }
      }

      const meta = this.normalizedPlatformMeta
      const fan = this.normalizedFanIdentity
      const medalName = pickString(meta.medal_name, meta.medalName, fan.badge_name, fan.badgeName, this.medalName)
      const medalLevel = pickNumber(meta.medal_level, meta.medalLevel, fan.level, this.medalLevel)
      const medalText = medalName ? `${medalName}${medalLevel > 0 ? ` ${medalLevel}` : ''}` : ''
      if (medalText) {
        badgeList.push(this.buildBadge('fans', medalText, 'bili'))
      }
      return badgeList
    },
    douyinBadges() {
      const badgeList = []
      const meta = this.normalizedPlatformMeta
      const fan = this.normalizedFanIdentity

      const membershipName = pickString(meta.membership_name, meta.membershipName)
      const membershipType = pickString(meta.membership_type, meta.membershipType).toLowerCase()
      const medalNameHint = pickString(
        this.medalName,
        meta.fans_badge_name,
        meta.fansBadgeName,
        fan.badge_name,
        fan.badgeName
      )
      const isStarGuard = membershipName.includes('星守护')
        || membershipType.includes('star')
        || membershipType.includes('xing')
        || medalNameHint === '星守护'
        || this.privilegeType > 0

      // 星守护：用「星守护」替换粉丝团位，舰长同级样式，不重复显示会员+粉丝团
      if (isStarGuard) {
        const level = pickNumber(meta.fans_badge_level, meta.fansBadgeLevel, fan.level, this.medalLevel)
        const text = level > 0 ? `星守护 ${level}` : '星守护'
        badgeList.push(this.buildBadge('membership', text, 'dy', ['badge--star-guard']))
        return badgeList
      }

      // 普通粉丝团：无专名，只显示「粉丝团」
      const fansBadgeLevel = pickNumber(meta.fans_badge_level, meta.fansBadgeLevel, fan.level, this.medalLevel)
      if (fansBadgeLevel > 0 || medalNameHint) {
        const text = fansBadgeLevel > 0 ? `粉丝团 ${fansBadgeLevel}` : '粉丝团'
        badgeList.push(this.buildBadge('fans', text, 'dy'))
      }
      return badgeList
    }
  },
  methods: {
    buildBadge(type, text, platform, extraClassNames = []) {
      const platformClass = platform === 'bili' ? 'badge--platform-bili' : 'badge--platform-dy'
      return {
        type,
        text,
        classNames: [
          `badge--type-${type}`,
          platformClass,
          ...extraClassNames
        ]
      }
    }
  }
}
</script>

<style scoped>
.identity-badges {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  margin-left: 6px;
  vertical-align: middle;
}

.identity-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 10px;
  padding: 0 6px;
  font-size: 11px;
  line-height: 18px;
  color: #fff;
  background: #666;
}

.badge--platform-bili.badge--type-guard {
  background: #c05f2f;
}

.badge--platform-bili.badge--type-fans {
  background: #a35085;
}

.badge--platform-dy.badge--type-membership {
  background: #6a5acd;
}

.badge--platform-dy.badge--type-fans {
  background: #d46b08;
}

/* 星守护：与 B 站舰长同色系，略加强对比 */
.badge--platform-dy.badge--star-guard {
  background: linear-gradient(135deg, #c05f2f 0%, #e8a87c 100%);
  box-shadow: 0 0 0 1px rgba(255, 220, 180, 0.35) inset;
  font-weight: 600;
}
</style>
