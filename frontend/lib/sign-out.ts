/**
 * NextAuth's signOut, loaded when it is called rather than with the page.
 *
 * The header's menu and the session-expiry timer are on every page but sign
 * out only on a click or an expiry, so next-auth/react (15 KB gzipped) stays
 * out of every page's first download.
 */
export const signOut = async (options?: { callbackUrl?: string }): Promise<void> => {
    const { signOut: nextAuthSignOut } = await import("next-auth/react");
    await nextAuthSignOut(options);
};
