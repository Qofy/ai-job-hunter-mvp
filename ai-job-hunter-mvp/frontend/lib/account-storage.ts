/** Namespace browser drafts by the authenticated principal; never used as authorization. */
export function accountStorageKey(userId: string, suffix: string) {
  return `jobpilot.user.${userId}.${suffix}`;
}
