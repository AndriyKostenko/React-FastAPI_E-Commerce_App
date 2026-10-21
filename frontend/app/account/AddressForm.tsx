"use client";

import { FieldValues, SubmitHandler, useForm } from "react-hook-form";
import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";
import type { AddressInput, SavedAddress } from "@/types/account";
import { isProvinceCode, POSTAL_CODE_PATTERN, PROVINCE_CODES, PROVINCES } from "@/utils/provinces";

interface AddressFormProps {
  /** The address being edited; absent for a new one. */
  address?: SavedAddress;
  /** True while the book's first address is being added: it becomes the default anyway. */
  isFirst: boolean;
  disabled: boolean;
  onSubmit: (input: AddressInput) => Promise<boolean>;
  onCancel: () => void;
}

// Bounds mirror user-service's AddressInput.
const RULES = {
  label: { maxLength: { value: 32, message: "At most 32 characters" } },
  name: {
    minLength: { value: 2, message: "At least 2 characters" },
    maxLength: { value: 100, message: "At most 100 characters" },
  },
  phone: { maxLength: { value: 32, message: "At most 32 characters" } },
  street: {
    minLength: { value: 3, message: "At least 3 characters" },
    maxLength: { value: 255, message: "At most 255 characters" },
  },
  city: { maxLength: { value: 100, message: "At most 100 characters" } },
  postal_code: { pattern: { value: POSTAL_CODE_PATTERN, message: "A Canadian postal code, like M5V 3L9" } },
} as const;

/** The form's values as AddressInput; the province select only offers valid codes. */
const toInput = (values: FieldValues): AddressInput | null => {
  if (!isProvinceCode(values.address_province)) return null;
  const phone = String(values.address_phone ?? "").trim();
  return {
    label: String(values.address_label).trim(),
    name: String(values.address_name).trim(),
    phone: phone || null,
    street: String(values.address_street).trim(),
    city: String(values.address_city).trim(),
    province: values.address_province,
    postal_code: String(values.address_postal_code).trim().toUpperCase(),
    is_default: Boolean(values.address_is_default),
  };
};

const AddressForm: React.FC<AddressFormProps> = ({ address, isFirst, disabled, onSubmit, onCancel }) => {
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<FieldValues>({
    // Field ids carry an "address_" prefix: the profile form on the same page
    // has its own "name" field, and DOM ids (label targets) must be unique.
    defaultValues: {
      address_label: address?.label ?? "Home",
      address_name: address?.name ?? "",
      address_phone: address?.phone ?? "",
      address_street: address?.street ?? "",
      address_city: address?.city ?? "",
      address_province: address?.province ?? "",
      address_postal_code: address?.postal_code ?? "",
      address_is_default: address?.is_default ?? false,
    },
  });

  const submit: SubmitHandler<FieldValues> = async (values) => {
    const input = toInput(values);
    if (input === null) {
      setError("address_province", { type: "validate", message: "Choose a province or territory" });
      return;
    }
    await onSubmit(input);
  };

  // The default can only move to another address, never be switched off
  // (see AddressService), so the box is fixed on for the default and the first.
  const defaultLocked = isFirst || Boolean(address?.is_default);

  return (
    <form onSubmit={handleSubmit(submit)} className="flex flex-col gap-4" noValidate>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Input id="address_label" label="Label (Home, Work)" disabled={disabled} register={register} errors={errors} validationRules={RULES.label} required glass />
        <Input id="address_name" label="Recipient name" disabled={disabled} register={register} errors={errors} validationRules={RULES.name} required glass />
        <div className="md:col-span-2">
          <Input id="address_street" label="Street address" disabled={disabled} register={register} errors={errors} validationRules={RULES.street} required glass />
        </div>
        <Input id="address_city" label="City" disabled={disabled} register={register} errors={errors} validationRules={RULES.city} required glass />
        <div className="w-full">
          <select
            id="address_province"
            aria-label="Province or territory"
            disabled={disabled}
            {...register("address_province", { required: "Choose a province or territory" })}
            className={`w-full p-4 bg-white/40 border rounded-2xl outline-none focus:ring-2 focus:ring-brand-lime disabled:opacity-70 ${
              errors.address_province ? "border-rose-400" : "border-white/30"
            }`}
          >
            <option value="" disabled>
              Province or territory
            </option>
            {PROVINCE_CODES.map((code) => (
              <option key={code} value={code}>
                {PROVINCES[code]}
              </option>
            ))}
          </select>
          {typeof errors.address_province?.message === "string" && (
            <p className="mt-1.5 px-1 text-xs text-rose-500">{errors.address_province.message}</p>
          )}
        </div>
        <Input id="address_postal_code" label="Postal code" disabled={disabled} register={register} errors={errors} validationRules={RULES.postal_code} required glass />
        <Input id="address_phone" label="Phone (optional)" type="tel" disabled={disabled} register={register} errors={errors} validationRules={RULES.phone} glass />
      </div>

      <label className="flex items-center gap-2 text-sm text-secondary">
        <input type="checkbox" disabled={disabled || defaultLocked} {...register("address_is_default")} checked={defaultLocked ? true : undefined} />
        {defaultLocked ? "Default address (used to fill in checkout)" : "Make this my default address"}
      </label>

      <div className="flex gap-3">
        <Button type="submit" disabled={disabled} variant="keyboard" size="md" label={address ? "Save address" : "Add address"} />
        <Button type="button" disabled={disabled} outline size="md" label="Cancel" onClick={onCancel} />
      </div>
    </form>
  );
};

export default AddressForm;
