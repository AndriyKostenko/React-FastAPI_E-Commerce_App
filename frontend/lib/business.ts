/**
 * Who runs the store, as the legal pages, the footer and the contact links
 * show it. One place, so a change of address or inbox cannot leave one page
 * out of date.
 */
export const BUSINESS = {
  name: "AIGEN",
  email: "a.kostenkouk@gmail.com",
  address: {
    street: "1055 11 Street SW",
    city: "Calgary",
    province: "Alberta",
    postalCode: "T2R 1G8",
    country: "Canada",
  },
} as const;

/** The date shown as "Last updated" on every legal page. */
export const LEGAL_PAGES_UPDATED = "October 18, 2026";

export const businessAddressLine = (): string => {
  const { street, city, province, postalCode, country } = BUSINESS.address;
  return `${street}, ${city}, ${province} ${postalCode}, ${country}`;
};

export interface SocialLink {
  label: string;
  href: string;
}

/**
 * Only an https URL counts: an unset or malformed value hides the link
 * instead of shipping one that goes nowhere.
 */
const httpsUrl = (value: string | undefined): string | null => {
  if (!value) return null;
  try {
    return new URL(value).protocol === "https:" ? value : null;
  } catch {
    return null;
  }
};

/**
 * The store's social profiles. NEXT_PUBLIC_* values are inlined at build
 * time, so each one is read by its literal name.
 */
export const socialLinks = (): SocialLink[] =>
  [
    {
      label: "Instagram",
      href: httpsUrl(process.env.NEXT_PUBLIC_INSTAGRAM_URL),
    },
    { label: "Facebook", href: httpsUrl(process.env.NEXT_PUBLIC_FACEBOOK_URL) },
  ].filter((link): link is SocialLink => link.href !== null);
