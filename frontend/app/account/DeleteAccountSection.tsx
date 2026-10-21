"use client";

import { useState } from "react";
import toast from "react-hot-toast";
import { signOut } from "@/lib/sign-out";
import Button from "@/components/ui/Button";
import { AccountApi } from "@/lib/account-api";
import { ApiError } from "@/lib/api-error";
import { clearUserScopedStorage } from "@/utils/client-storage";

const CONFIRMATION_WORD = "DELETE";

/**
 * Delete the account. The backend anonymises the user, removes saved
 * addresses and ends every session; orders stay, as the business records
 * they are. Confirmed by typing a word rather than a browser dialog.
 */
const DeleteAccountSection: React.FC<{ userId: string }> = ({ userId }) => {
  const [confirmation, setConfirmation] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);

  const deleteAccount = async () => {
    setIsDeleting(true);
    try {
      await AccountApi.deleteAccount(userId);
      toast.success("Your account has been deleted.");
      clearUserScopedStorage();
      await signOut({ callbackUrl: "/" });
    } catch (error) {
      toast.error(ApiError.from(error, "Could not delete your account.").message);
      setIsDeleting(false);
    }
  };

  return (
    <section className="glass-card p-6 md:p-8 flex flex-col gap-4 border border-rose-200">
      <div>
        <h2 className="font-bold text-xl text-rose-600">Delete account</h2>
        <p className="text-sm text-secondary">
          Your name, email, phone and saved addresses are removed and you are signed out everywhere. Orders you
          placed are kept for our records. This cannot be undone.
        </p>
      </div>
      <label className="text-sm flex flex-col gap-2 md:w-80">
        <span>
          Type <span className="font-mono font-semibold">{CONFIRMATION_WORD}</span> to confirm
        </span>
        <input
          value={confirmation}
          onChange={(event) => setConfirmation(event.target.value)}
          disabled={isDeleting}
          className="p-3 bg-white/40 border border-white/30 rounded-2xl outline-none focus:ring-2 focus:ring-rose-400"
          autoComplete="off"
        />
      </label>
      <div className="md:w-48">
        <Button
          size="md"
          label={isDeleting ? "Deleting..." : "Delete my account"}
          disabled={isDeleting || confirmation !== CONFIRMATION_WORD}
          custom="!bg-rose-600 !border-rose-600"
          onClick={deleteAccount}
        />
      </div>
    </section>
  );
};

export default DeleteAccountSection;
