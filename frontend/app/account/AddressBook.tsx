"use client";

import { useState } from "react";
import { MdAdd, MdDelete, MdEdit, MdStar, MdStarOutline } from "react-icons/md";
import Button from "@/components/ui/Button";
import { useAddressBook } from "@/hooks/useAddressBook";
import type { AddressInput, SavedAddress } from "@/types/account";
import { PROVINCES } from "@/utils/provinces";
import AddressForm from "./AddressForm";

/** Which form is open: none, a new address, or one address being edited. */
type Editing = { kind: "none" } | { kind: "new" } | { kind: "edit"; id: string };

const MAX_ADDRESSES = 10; // AddressService.MAX_ADDRESSES_PER_USER

const AddressBook: React.FC<{ initialAddresses: SavedAddress[] }> = ({ initialAddresses }) => {
  const { addresses, busyId, create, replace, makeDefault, remove } = useAddressBook(initialAddresses);
  const [editing, setEditing] = useState<Editing>({ kind: "none" });
  // Deleting asks once inline instead of a browser dialog.
  const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null);

  const close = () => setEditing({ kind: "none" });
  const submitNew = async (input: AddressInput) => {
    const saved = await create(input);
    if (saved) close();
    return saved;
  };
  const submitEdit = (id: string) => async (input: AddressInput) => {
    const saved = await replace(id, input);
    if (saved) close();
    return saved;
  };

  return (
    <section className="glass-card p-6 md:p-8 flex flex-col gap-5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="font-bold text-xl text-primary">Address book</h2>
          <p className="text-sm text-secondary">Your default address fills in checkout. We ship within Canada only.</p>
        </div>
        {editing.kind === "none" && addresses.length < MAX_ADDRESSES && (
          <div>
            <Button variant="keyboard" size="md" icon={MdAdd} label="Add" onClick={() => setEditing({ kind: "new" })} />
          </div>
        )}
      </div>

      {editing.kind === "new" && (
        <AddressForm isFirst={addresses.length === 0} disabled={busyId === "new"} onSubmit={submitNew} onCancel={close} />
      )}

      {addresses.length === 0 && editing.kind !== "new" && (
        <p className="text-sm text-secondary">No saved addresses yet.</p>
      )}

      <ul className="flex flex-col gap-3">
        {addresses.map((address) =>
          editing.kind === "edit" && editing.id === address.id ? (
            <li key={address.id} className="rounded-2xl border border-white/30 bg-white/30 p-4">
              <AddressForm
                address={address}
                isFirst={false}
                disabled={busyId === address.id}
                onSubmit={submitEdit(address.id)}
                onCancel={close}
              />
            </li>
          ) : (
            <li
              key={address.id}
              className="rounded-2xl border border-white/30 bg-white/30 p-4 flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3"
            >
              <div className="text-sm">
                <p className="font-semibold text-primary flex items-center gap-2">
                  {address.label}
                  {address.is_default && (
                    <span className="text-[10px] uppercase tracking-wider bg-brand-lime/60 rounded-full px-2 py-0.5">
                      Default
                    </span>
                  )}
                </p>
                <p>{address.name}</p>
                <p>{address.street}</p>
                <p>
                  {address.city}, {PROVINCES[address.province] ?? address.province} {address.postal_code}
                </p>
                {address.phone && <p className="text-secondary">{address.phone}</p>}
              </div>

              {confirmingDelete === address.id ? (
                <div className="flex items-center gap-2 text-sm">
                  <span>Delete this address?</span>
                  <Button
                    size="sm"
                    label="Delete"
                    disabled={busyId === address.id}
                    onClick={async () => {
                      await remove(address.id);
                      setConfirmingDelete(null);
                    }}
                  />
                  <Button size="sm" outline label="Keep" onClick={() => setConfirmingDelete(null)} />
                </div>
              ) : (
                <div className="flex gap-2">
                  {!address.is_default && (
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={MdStarOutline}
                      aria-label="Make default"
                      title="Make default"
                      disabled={busyId !== null}
                      onClick={() => makeDefault(address.id)}
                    />
                  )}
                  {address.is_default && (
                    <span className="p-1.5 text-primary" title="Default address">
                      <MdStar size={16} />
                    </span>
                  )}
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={MdEdit}
                    aria-label="Edit"
                    title="Edit"
                    disabled={busyId !== null || editing.kind !== "none"}
                    onClick={() => setEditing({ kind: "edit", id: address.id })}
                  />
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={MdDelete}
                    aria-label="Delete"
                    title="Delete"
                    disabled={busyId !== null}
                    onClick={() => setConfirmingDelete(address.id)}
                  />
                </div>
              )}
            </li>
          ),
        )}
      </ul>
    </section>
  );
};

export default AddressBook;
