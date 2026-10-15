"use client";

import { useCallback, useState } from "react";
import toast from "react-hot-toast";
import { AccountApi } from "@/lib/account-api";
import { ApiError } from "@/lib/api-error";
import type { AddressInput, SavedAddress } from "@/types/account";

/**
 * The address book's state and actions (a Facade over AccountApi).
 *
 * After every change the list is read again from the backend rather than
 * patched locally: one change can move the default between two addresses
 * (or promote another on delete), and the server is the one that decides.
 */
export const useAddressBook = (initial: SavedAddress[]) => {
  const [addresses, setAddresses] = useState<SavedAddress[]>(initial);
  const [busyId, setBusyId] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setAddresses(await AccountApi.listAddresses());
  }, []);

  /** Runs one change, shows its outcome, and reloads. Resolves to whether it succeeded. */
  const run = useCallback(
    async (key: string, action: () => Promise<unknown>, success: string, fallback: string): Promise<boolean> => {
      setBusyId(key);
      try {
        await action();
        await reload();
        toast.success(success);
        return true;
      } catch (error) {
        toast.error(ApiError.from(error, fallback).message);
        return false;
      } finally {
        setBusyId(null);
      }
    },
    [reload],
  );

  const create = useCallback(
    (input: AddressInput) =>
      run("new", () => AccountApi.createAddress(input), "Address saved", "Could not save the address."),
    [run],
  );

  const replace = useCallback(
    (id: string, input: AddressInput) =>
      run(id, () => AccountApi.replaceAddress(id, input), "Address updated", "Could not save the address."),
    [run],
  );

  const makeDefault = useCallback(
    (id: string) =>
      run(id, () => AccountApi.makeDefault(id), "Default address changed", "Could not change the default."),
    [run],
  );

  const remove = useCallback(
    (id: string) =>
      run(id, () => AccountApi.deleteAddress(id), "Address deleted", "Could not delete the address."),
    [run],
  );

  return { addresses, busyId, create, replace, makeDefault, remove };
};
