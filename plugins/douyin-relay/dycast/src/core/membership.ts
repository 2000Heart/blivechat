import type { Image, User } from './model';

const NAME_TOKEN = '星守护';
const URI_TOKENS = ['xingshouhu', 'star_guard', 'star-guard'] as const;
const MEMBER_NAME = '会员';
const MEMBER_URI_TOKEN = 'subscribe_new';

function asImageList(value: Image | Image[] | undefined): Image[] {
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
}

function textHasStarGuard(text: string | undefined): boolean {
  if (!text) return false;
  const s = text.trim();
  if (!s) return false;
  if (s.includes(NAME_TOKEN)) return true;
  const lower = s.toLowerCase();
  return URI_TOKENS.some((t) => lower.includes(t));
}

function textHas(text: string | undefined, token: string): boolean {
  return !!text && text.toLowerCase().includes(token);
}

function imageHas(img: Image | undefined, match: (text: string | undefined) => boolean): boolean {
  if (!img) return false;
  if (match(img.content?.name)) return true;
  if (match(img.content?.alternativeText)) return true;
  if (match(img.uri)) return true;
  return (img.urlList || []).some((url) => match(url));
}

function imageLooksLikeStarGuard(img: Image | undefined): boolean {
  return imageHas(img, textHasStarGuard);
}

function imageLooksLikeMember(img: Image | undefined): boolean {
  return imageHas(img, (text) => textHas(text, MEMBER_NAME) || textHas(text, MEMBER_URI_TOKEN));
}

function userBadges(user: User): Image[] {
  return [
    ...asImageList(user.badgeImageList),
    ...asImageList(user.badgeImageListV2),
    ...asImageList(user.medal),
    ...asImageList(user.mediaBadgeImageList),
    ...(user.realTimeIcons || []),
    ...(user.newRealTimeIcons || [])
  ];
}

export function pickUserMembership(
  user?: User
): {
  starGuard?: { membershipType: 'star_guard'; membershipName: '星守护' };
  member?: { membershipType: 'member'; membershipName: '会员' };
} | undefined {
  if (!user) return undefined;
  const badges = userBadges(user);
  const found: {
    starGuard?: { membershipType: 'star_guard'; membershipName: '星守护' };
    member?: { membershipType: 'member'; membershipName: '会员' };
  } = {};
  if (badges.some(imageLooksLikeStarGuard)) {
    found.starGuard = { membershipType: 'star_guard', membershipName: '星守护' };
  }
  if (badges.some(imageLooksLikeMember)) {
    found.member = { membershipType: 'member', membershipName: '会员' };
  }
  if (!found.starGuard && !found.member) return undefined;
  return found;
}

export function pickStarGuardMembership(
  user?: User
): { membershipType: 'star_guard'; membershipName: '星守护' } | undefined {
  return pickUserMembership(user)?.starGuard;
}
