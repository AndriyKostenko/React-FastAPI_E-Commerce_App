"use client";

import { useState } from "react";
import Link from "next/link";
import toast from "react-hot-toast";
import { signOut } from "next-auth/react";
import { FieldValues, SubmitHandler, useForm } from "react-hook-form";
import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";
import { AccountApi } from "@/lib/account-api";
import { ApiError } from "@/lib/api-error";
import { clearUserScopedStorage } from "@/utils/client-storage";

// Mirrors PasswordChangeRequest.new_password in user-service.
const NEW_PASSWORD_RULES = {
  minLength: { value: 8, message: "At least 8 characters" },
  maxLength: { value: 100, message: "At most 100 characters" },
};

/**
 * Change the password with the current one. The backend ends every session
 * on success, this one included, so the user is signed out and signs in again.
 */
const PasswordSection: React.FC = () => {
  const [isSaving, setIsSaving] = useState(false);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<FieldValues>({
    defaultValues: { current_password: "", new_password: "", repeated_password: "" },
  });

  const onSubmit: SubmitHandler<FieldValues> = async (values) => {
    if (values.new_password !== values.repeated_password) {
      setError("repeated_password", { type: "validate", message: "Passwords do not match" });
      return;
    }
    setIsSaving(true);
    try {
      await AccountApi.changePassword({
        current_password: String(values.current_password),
        new_password: String(values.new_password),
      });
      toast.success("Password changed. Sign in with your new password.");
      clearUserScopedStorage();
      await signOut({ callbackUrl: "/login" });
    } catch (error) {
      const apiError = ApiError.from(error, "Could not change your password.");
      const fieldError = apiError.fieldErrors.find((e) => e.field === "new_password");
      if (fieldError) setError("new_password", { type: "server", message: fieldError.message });
      else if (apiError.status === 400 && apiError.message.toLowerCase().includes("current")) {
        setError("current_password", { type: "server", message: apiError.message });
      } else toast.error(apiError.message);
      setIsSaving(false);
    }
  };

  return (
    <section className="glass-card p-6 md:p-8 flex flex-col gap-5">
      <div>
        <h2 className="font-bold text-xl text-primary">Password</h2>
        <p className="text-sm text-secondary">
          Changing it signs you out everywhere. Signed up with Google and never set one?{" "}
          <Link href="/forgot-password" className="text-primary underline underline-offset-2">
            Set a password by email
          </Link>
          .
        </p>
      </div>
      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Input id="current_password" label="Current password" type="password" disabled={isSaving} register={register} errors={errors} required glass />
          <Input id="new_password" label="New password" type="password" disabled={isSaving} register={register} errors={errors} validationRules={NEW_PASSWORD_RULES} required glass />
          <Input id="repeated_password" label="Repeat new password" type="password" disabled={isSaving} register={register} errors={errors} required glass />
        </div>
        <div className="md:w-48">
          <Button type="submit" variant="keyboard" size="md" disabled={isSaving} label={isSaving ? "Changing..." : "Change password"} />
        </div>
      </form>
    </section>
  );
};

export default PasswordSection;
