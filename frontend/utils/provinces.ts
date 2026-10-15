import type { ProvinceCode } from "@/types/account";

/**
 * Canada's provinces and territories, the only regions the store ships to.
 * The codes match user-service's and order-service's `PROVINCES`.
 */
export const PROVINCES: Readonly<Record<ProvinceCode, string>> = {
  AB: "Alberta",
  BC: "British Columbia",
  MB: "Manitoba",
  NB: "New Brunswick",
  NL: "Newfoundland and Labrador",
  NS: "Nova Scotia",
  NT: "Northwest Territories",
  NU: "Nunavut",
  ON: "Ontario",
  PE: "Prince Edward Island",
  QC: "Quebec",
  SK: "Saskatchewan",
  YT: "Yukon",
};

export const PROVINCE_CODES = Object.keys(PROVINCES) as ProvinceCode[];

export const isProvinceCode = (value: unknown): value is ProvinceCode =>
  typeof value === "string" && value in PROVINCES;

/** A1A 1A1, the same pattern the backend checks (letters D F I O Q U never appear; W Z never lead). */
export const POSTAL_CODE_PATTERN = /^[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z] ?\d[ABCEGHJ-NPRSTV-Z]\d$/i;
