/**
 * The account page's data, as user-service sends and accepts it.
 * Field names follow the backend (snake_case) so no mapping is needed.
 */

/** user-service `UserInfo`: what GET/PATCH /users/{id} return. */
export interface AccountProfile {
  id: string;
  name: string;
  email: string;
  role: string;
  phone_number: string | null;
  image: string | null;
  date_created: string;
  date_updated: string | null;
  is_verified: boolean;
  is_active: boolean;
}

/** user-service `UserBasicUpdate`: only the fields being changed. */
export interface ProfileUpdate {
  name?: string;
  phone_number?: string | null;
}

/** user-service `PasswordChangeRequest`. */
export interface PasswordChange {
  current_password: string;
  new_password: string;
}

/** user-service `PasswordUpdateResponse`. */
export interface PasswordChangeResult {
  detail: string;
  email: string;
}

/** ISO 3166-2:CA province and territory codes, the only regions the store ships to. */
export type ProvinceCode =
  | "AB"
  | "BC"
  | "MB"
  | "NB"
  | "NL"
  | "NS"
  | "NT"
  | "NU"
  | "ON"
  | "PE"
  | "QC"
  | "SK"
  | "YT";

/** user-service `AddressInput`: a saved address as the form sends it (country is always Canada). */
export interface AddressInput {
  label: string;
  name: string;
  phone: string | null;
  street: string;
  city: string;
  province: ProvinceCode;
  postal_code: string;
  is_default: boolean;
}

/** user-service `AddressRead`: a saved address, normalised by the backend. */
export interface SavedAddress {
  id: string;
  label: string;
  name: string;
  phone: string | null;
  street: string;
  city: string;
  province: ProvinceCode;
  postal_code: string;
  country: string;
  country_code: string;
  is_default: boolean;
  date_created: string;
  date_updated: string | null;
}
