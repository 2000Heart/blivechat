import type { Image, User } from './model';

const NAME_TOKEN = '星守护';
const URI_TOKENS = ['xingshouhu', 'star_guard', 'star-guard'] as const;

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

function imageLooksLikeStarGuard(img: Image | undefined): boolean {
  if (!img) return false;
  if (textHasStarGuard(img.content?.name)) return true;
  if (textHasStarGuard(img.content?.alternativeText)) return true;
  if (textHasStarGuard(img.uri)) return true;
  for (const url of img.urlList || []) {
    if (textHasStarGuard(url)) return true;
  }
  return false;
}

export function pickStarGuardMembership(
  user?: User
): { membershipType: 'star_guard'; membershipName: '星守护' } | undefined {
  if (!user) return undefined;
  const badges = [
    ...asImageList(user.badgeImageList),
    ...asImageList(user.badgeImageListV2),
    ...asImageList(user.medal),
    ...(user.realTimeIcons || []),
    ...(user.newRealTimeIcons || [])
  ];
  if (badges.some(imageLooksLikeStarGuard)) {
    return { membershipType: 'star_guard', membershipName: '星守护' };
  }
  return undefined;
}
