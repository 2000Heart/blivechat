import assert from 'node:assert/strict'
import test from 'node:test'
import { pickUserMembership } from './membership.ts'

test('subscribe badge is 会员', () => {
  const found = pickUserMembership({
    badgeImageList: [{ uri: 'webcast/subscribe_new_3x.png', content: { name: '勋章' } }]
  })
  assert.deepEqual(found, { member: { membershipType: 'member', membershipName: '会员' } })
})

test('subscribe badge in the image url is 会员', () => {
  const found = pickUserMembership({
    mediaBadgeImageList: { urlList: ['https://p3.example.com/webcast/subscribe_new_v3.png'] }
  })
  assert.equal(found?.member?.membershipName, '会员')
})

test('star guard and 会员 are both kept', () => {
  const found = pickUserMembership({
    badgeImageList: [
      { uri: 'webcast/subscribe_new_v3.png' },
      { uri: 'webcast/star_guard_advanced_badge_13_xmp.png' }
    ]
  })
  assert.equal(found?.starGuard?.membershipName, '星守护')
  assert.equal(found?.member?.membershipName, '会员')
})

test('fans and honor badges are not 会员', () => {
  const found = pickUserMembership({
    badgeImageList: [
      { uri: 'webcast/fansclub_new_advanced_badge_11_xmp.png', content: { alternativeText: '粉丝团等级11级勋章' } },
      { uri: 'webcast/new_user_grade_level_v1_20.png', content: { name: '荣誉等级20级勋章' } }
    ]
  })
  assert.equal(found, undefined)
})
