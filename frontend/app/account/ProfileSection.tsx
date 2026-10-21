"use client";

import { useState } from "react";
import toast from "react-hot-toast";
import { FieldValues, SubmitHandler, useForm } from "react-hook-form";
import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";
import { AccountApi } from "@/lib/account-api";
import { ApiError } from "@/lib/api-error";
import { savedProfileStore } from "@/lib/saved-profile-store";
import type { AccountProfile, ProfileUpdate } from "@/types/account";
import AvatarPicker from "./AvatarPicker";

// Bounds mirror user-service's UserBasicUpdate.
const RULES = {
  name: {
    minLength: { value: 2, message: "At least 2 characters" },
    maxLength: { value: 50, message: "At most 50 characters" },
  },
  phone_number: { maxLength: { value: 32, message: "At most 32 characters" } },
} as const;

const ProfileSection: React.FC<{ profile: AccountProfile }> = ({ profile }) => {
  const [isSaving, setIsSaving] = useState(false);
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors, isDirty },
  } = useForm<FieldValues>({
    defaultValues: { name: profile.name, phone_number: profile.phone_number ?? "" },
  });

  const onSubmit: SubmitHandler<FieldValues> = async (values) => {
    const phone = String(values.phone_number ?? "").trim();
    const update: ProfileUpdate = { name: String(values.name).trim(), phone_number: phone || null };
    setIsSaving(true);
    try {
      const saved = await AccountApi.updateProfile(profile.id, update);
      reset({ name: saved.name, phone_number: saved.phone_number ?? "" });
      toast.success("Profile saved");
      // The header shows it from here: no refresh, which would read the profile twice more.
      savedProfileStore.publish(saved.id, saved);
    } catch (error) {
      const apiError = ApiError.from(error, "Could not save your profile.");
      const fieldError = apiError.fieldErrors.find((e) => e.field === "name" || e.field === "phone_number");
      if (fieldError) setError(fieldError.field, { type: "server", message: fieldError.message });
      else toast.error(apiError.message);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <section className="glass-card p-6 md:p-8 flex flex-col gap-5">
      <div>
        <h2 className="font-bold text-xl text-primary">Profile</h2>
        <p className="text-sm text-secondary">
          Signed in as <span className="font-semibold">{profile.email}</span>
        </p>
      </div>
      <AvatarPicker image={profile.image} name={profile.name} />
      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input id="name" label="Name" disabled={isSaving} register={register} errors={errors} validationRules={RULES.name} required glass />
          <Input id="phone_number" label="Phone (optional)" type="tel" disabled={isSaving} register={register} errors={errors} validationRules={RULES.phone_number} glass />
        </div>
        <div className="md:w-48">
          <Button type="submit" variant="keyboard" size="md" disabled={isSaving || !isDirty} label={isSaving ? "Saving..." : "Save profile"} />
        </div>
      </form>
    </section>
  );
};

export default ProfileSection;
