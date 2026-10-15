"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Avatar } from "@mui/material";
import toast from "react-hot-toast";
import Button from "@/components/ui/Button";
import { AccountApi } from "@/lib/account-api";
import { ApiError } from "@/lib/api-error";

// The same limits user-service applies; checked here only to fail fast.
const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"] as const;
const MAX_BYTES = 5 * 1024 * 1024;

interface AvatarPickerProps {
  image: string | null;
  name: string;
}

/** Shows the avatar and lets the user replace or remove it. */
const AvatarPicker: React.FC<AvatarPickerProps> = ({ image, name }) => {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [current, setCurrent] = useState<string | null>(image);
  const [isBusy, setIsBusy] = useState(false);

  const run = async (action: () => Promise<{ image: string | null }>, success: string, fallback: string) => {
    setIsBusy(true);
    try {
      const profile = await action();
      setCurrent(profile.image);
      toast.success(success);
      router.refresh();
    } catch (error) {
      toast.error(ApiError.from(error, fallback).message);
    } finally {
      setIsBusy(false);
      if (input.current) input.current.value = "";
    }
  };

  const onFileChosen = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!(ACCEPTED_TYPES as readonly string[]).includes(file.type)) {
      toast.error("Choose a JPEG, PNG or WebP image.");
      return;
    }
    if (file.size > MAX_BYTES) {
      toast.error("The image must be at most 5 MB.");
      return;
    }
    void run(() => AccountApi.uploadAvatar(file), "Picture updated", "Could not upload your picture.");
  };

  return (
    <div className="flex items-center gap-4">
      <Avatar src={current ?? undefined} alt={name} sx={{ width: 72, height: 72 }} />
      <div className="flex flex-wrap gap-2">
        <input
          ref={input}
          type="file"
          accept={ACCEPTED_TYPES.join(",")}
          className="hidden"
          onChange={onFileChosen}
          aria-label="Choose a profile picture"
        />
        <div>
          <Button
            size="sm"
            variant="keyboard"
            disabled={isBusy}
            label={isBusy ? "Saving..." : current ? "Change picture" : "Add picture"}
            onClick={() => input.current?.click()}
          />
        </div>
        {current && (
          <div>
            <Button
              size="sm"
              outline
              disabled={isBusy}
              label="Remove"
              onClick={() => run(() => AccountApi.removeAvatar(), "Picture removed", "Could not remove your picture.")}
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default AvatarPicker;
