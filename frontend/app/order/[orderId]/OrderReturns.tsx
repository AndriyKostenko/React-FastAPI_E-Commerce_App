"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { MdClose } from "react-icons/md";
import Button from "@/components/ui/Button";
import { ApiError } from "@/lib/api-error";
import { ReturnsApi } from "@/lib/returns-api";
import {
  DESCRIPTION_MAX,
  RETURN_PHOTO_LIMITS,
  RETURN_REASONS,
  ReturnDraft,
  photoProblem,
} from "@/lib/return-draft";
import type { OrderLineView } from "@/types/order";
import type { OrderReturnsData, ReturnRequestView, ReturnStatus } from "@/types/returns";

const dateOnly = (value: string): string =>
  new Date(value).toLocaleDateString("en-CA", { year: "numeric", month: "long", day: "numeric" });

const STATUS_VIEW: Readonly<Record<ReturnStatus, { label: string; tone: string }>> = {
  requested: { label: "Waiting for review", tone: "bg-amber-100 text-amber-800" },
  approved: { label: "Approved", tone: "bg-sky-100 text-sky-800" },
  completed: { label: "Refunded", tone: "bg-green-100 text-green-800" },
  rejected: { label: "Declined", tone: "bg-rose-100 text-rose-800" },
  cancelled: { label: "Withdrawn", tone: "bg-slate-200 text-slate-700" },
};

const FAULT_NOTE = {
  seller: "Our mistake: these items are refunded in full, shipping included. Please add a photo of the problem.",
  customer: "The original shipping is not refunded, and sending the items back is at your cost.",
} as const;

const FIELD_CLASS =
  "p-3 bg-white/40 border border-white/30 rounded-2xl outline-none focus:ring-2 focus:ring-primary/40";

/** A chosen photo before it is sent. */
const PhotoThumb: React.FC<{ file: File; onRemove: () => void; disabled: boolean }> = ({ file, onRemove, disabled }) => {
  // The preview URL is made when the element attaches and revoked when it
  // detaches (a React 19 ref cleanup). Strict Mode attaches twice in dev, and
  // each attach makes its own URL, so a revoked one is never shown again.
  const attachPreview = useCallback(
    (element: HTMLSpanElement | null) => {
      if (!element) return;
      const url = URL.createObjectURL(file);
      element.style.backgroundImage = `url("${url}")`;
      return () => URL.revokeObjectURL(url);
    },
    [file],
  );
  return (
    <li className="relative">
      <span ref={attachPreview} role="img" aria-label={file.name} className="block h-20 w-20 rounded-xl bg-cover bg-center" />
      <button
        type="button"
        onClick={onRemove}
        disabled={disabled}
        aria-label={`Remove ${file.name}`}
        className="absolute -top-2 -right-2 rounded-full bg-white p-1 shadow text-slate-700"
      >
        <MdClose size={14} />
      </button>
    </li>
  );
};

/** One return already asked for, with what happens next. */
const ReturnCard: React.FC<{
  record: ReturnRequestView;
  names: ReadonlyMap<string, string>;
  onWithdraw: (record: ReturnRequestView) => void;
  busy: boolean;
}> = ({ record, names, onWithdraw, busy }) => {
  const status = STATUS_VIEW[record.status];
  // Approved, with goods still to come back before they are refunded.
  const awaitingGoods = record.status === "approved" && record.lines.some((line) => line.ships_back && !line.refunded);
  return (
    <li className="rounded-2xl border border-white/30 bg-white/30 p-4 flex flex-col gap-2 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-semibold text-primary">{RETURN_REASONS[record.reason].label}</span>
        <span className={`text-xs font-semibold rounded-full px-2.5 py-1 ${status.tone}`}>{status.label}</span>
      </div>
      <ul className="text-secondary">
        {record.lines.map((line) => (
          <li key={line.order_item_id}>
            {line.quantity} × {names.get(line.order_item_id) ?? "Item"}
          </li>
        ))}
      </ul>
      <p className="text-secondary">Asked on {dateOnly(record.date_created)}</p>
      {awaitingGoods && (
        <p>We emailed you the address to send the items to. They are refunded once they arrive.</p>
      )}
      {record.admin_note && <p className="italic">“{record.admin_note}”</p>}
      {record.status === "requested" && (
        <div className="w-40">
          <Button size="sm" outline disabled={busy} label="Withdraw" onClick={() => onWithdraw(record)} />
        </div>
      )}
    </li>
  );
};

interface ReturnFormProps {
  orderId: string;
  draft: ReturnDraft;
  onChange: (draft: ReturnDraft) => void;
  onSent: () => void;
  onCancel: () => void;
}

const ReturnForm: React.FC<ReturnFormProps> = ({ orderId, draft, onChange, onSent, onCancel }) => {
  const fileInput = useRef<HTMLInputElement>(null);
  const [isSending, setIsSending] = useState(false);
  // Problems are shown only once the customer has tried to send.
  const [triedToSend, setTriedToSend] = useState(false);

  const onFilesChosen = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    const accepted = files.filter((file) => {
      const problem = photoProblem(file);
      if (problem) toast.error(problem);
      return problem === null;
    });
    const room = RETURN_PHOTO_LIMITS.maxCount - draft.photos.length;
    if (accepted.length > room) toast.error(`At most ${RETURN_PHOTO_LIMITS.maxCount} photos can be attached.`);
    onChange(draft.withPhotosAdded(accepted));
  };

  const send = async (event: React.FormEvent) => {
    event.preventDefault();
    setTriedToSend(true);
    if (draft.problems.length > 0 || isSending) return;
    setIsSending(true);
    try {
      await ReturnsApi.request(orderId, draft.toRequest(), draft.photos);
      toast.success("Return requested. We will email you once it is reviewed.");
      onSent();
    } catch (error) {
      toast.error(ApiError.from(error, "Could not send your return request.").message);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <form onSubmit={send} className="flex flex-col gap-5">
      <fieldset className="flex flex-col gap-2">
        <legend className="font-semibold mb-2">What would you like to return?</legend>
        {draft.returnableLines.map((line) => {
          const chosen = draft.quantityOf(line.order_item_id);
          return (
            <div key={line.order_item_id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/30 bg-white/30 p-3">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={chosen > 0}
                  disabled={isSending}
                  onChange={(event) => onChange(draft.withQuantity(line.order_item_id, event.target.checked ? 1 : 0))}
                />
                <span>
                  {line.product_name}
                  {line.return_by && <span className="block text-xs text-secondary">Return by {dateOnly(line.return_by)}</span>}
                </span>
              </label>
              {line.returnable_quantity > 1 && chosen > 0 && (
                <label className="flex items-center gap-2 text-sm">
                  Units
                  <select
                    value={chosen}
                    disabled={isSending}
                    onChange={(event) => onChange(draft.withQuantity(line.order_item_id, Number(event.target.value)))}
                    className="p-1.5 bg-white/40 border border-white/30 rounded-xl"
                  >
                    {Array.from({ length: line.returnable_quantity }, (_, index) => index + 1).map((count) => (
                      <option key={count} value={count}>
                        {count}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>
          );
        })}
      </fieldset>

      <fieldset className="flex flex-col gap-2">
        <legend className="font-semibold mb-2">Why are you returning it?</legend>
        {draft.allowedReasons.map((reason) => (
          <label key={reason} className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="return-reason"
              value={reason}
              checked={draft.reason === reason}
              disabled={isSending}
              onChange={() => onChange(draft.withReason(reason))}
            />
            {RETURN_REASONS[reason].label}
          </label>
        ))}
        {/* Fewer reasons than usual: a made-to-order print is only returned for our mistakes. */}
        {draft.allowedReasons.length < Object.keys(RETURN_REASONS).length && (
          <p className="text-xs text-secondary">Custom prints are made for you, so they can be returned only when something is wrong with them.</p>
        )}
        {draft.reason && <p className="text-sm text-secondary">{FAULT_NOTE[RETURN_REASONS[draft.reason].fault]}</p>}
      </fieldset>

      <label className="flex flex-col gap-2 text-sm">
        <span className="font-semibold text-base">What happened?</span>
        <textarea
          value={draft.description}
          onChange={(event) => onChange(draft.withDescription(event.target.value))}
          disabled={isSending}
          rows={4}
          maxLength={DESCRIPTION_MAX}
          className={FIELD_CLASS}
        />
      </label>

      <div className="flex flex-col gap-2">
        <span className="font-semibold">
          Photos <span className="text-sm font-normal text-secondary">({draft.needsPhoto ? "required" : "optional"}, up to {RETURN_PHOTO_LIMITS.maxCount}, JPEG, PNG or WebP, 5 MB each)</span>
        </span>
        {draft.photos.length > 0 && (
          <ul className="flex flex-wrap gap-3">
            {draft.photos.map((file, index) => (
              <PhotoThumb key={`${file.name}-${index}`} file={file} disabled={isSending} onRemove={() => onChange(draft.withoutPhoto(index))} />
            ))}
          </ul>
        )}
        <input
          ref={fileInput}
          type="file"
          multiple
          accept={RETURN_PHOTO_LIMITS.types.join(",")}
          className="hidden"
          onChange={onFilesChosen}
          aria-label="Add photos"
        />
        {draft.photos.length < RETURN_PHOTO_LIMITS.maxCount && (
          <div className="w-40">
            <Button size="sm" outline disabled={isSending} label="Add photos" onClick={() => fileInput.current?.click()} />
          </div>
        )}
      </div>

      {triedToSend && draft.problems.length > 0 && (
        <ul className="text-sm text-rose-600 list-disc pl-5">
          {draft.problems.map((problem) => (
            <li key={problem}>{problem}</li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap gap-3">
        <div className="w-48">
          <Button type="submit" size="md" disabled={isSending} label={isSending ? "Sending..." : "Request return"} />
        </div>
        <div className="w-32">
          <Button size="md" outline disabled={isSending} label="Cancel" onClick={onCancel} />
        </div>
      </div>
    </form>
  );
};

/**
 * The order's returns: those already asked for, and a form for the units that
 * can still be returned. Eligibility comes from order-service, so the form
 * offers exactly what a request would be accepted for; the server checks it
 * all again. After a change the page reads both from the server again.
 */
const OrderReturns: React.FC<{ orderId: string; lines: OrderLineView[]; data: OrderReturnsData }> = ({ orderId, lines, data }) => {
  const router = useRouter();
  const [draft, setDraft] = useState<ReturnDraft | null>(null);
  const [withdrawing, setWithdrawing] = useState<string | null>(null);
  const names = useMemo(() => new Map(lines.map((line) => [line.order_item_id, line.product_name])), [lines]);
  const canRequest = ReturnDraft.start(data.eligibility).returnableLines.length > 0;

  const withdraw = async (record: ReturnRequestView) => {
    setWithdrawing(record.id);
    try {
      await ReturnsApi.cancel(orderId, record.id);
      toast.success("Return withdrawn.");
      router.refresh();
    } catch (error) {
      toast.error(ApiError.from(error, "Could not withdraw the return.").message);
    } finally {
      setWithdrawing(null);
    }
  };

  // Lines a return still in progress covers: its card already says what is
  // happening, and the backend's "already returned or refunded" would not.
  const inOpenReturn = new Set(
    data.returns
      .filter((record) => record.status === "requested" || record.status === "approved")
      .flatMap((record) => record.lines.map((line) => line.order_item_id)),
  );
  // Delivered lines only: before delivery there is nothing to explain yet.
  const closedLines = data.eligibility.lines.filter(
    (line) =>
      line.returnable_quantity === 0 &&
      line.return_by !== null &&
      line.unavailable_reason &&
      !inOpenReturn.has(line.order_item_id),
  );

  return (
    <section className="glass-card p-6 flex flex-col gap-4">
      <div>
        <h2 className="font-bold text-lg text-primary">Returns</h2>
        <p className="text-sm text-secondary">
          Delivered items can be returned within {data.eligibility.window_days} days of delivery.
        </p>
      </div>

      {data.returns.length > 0 && (
        <ul className="flex flex-col gap-3">
          {data.returns.map((record) => (
            <ReturnCard key={record.id} record={record} names={names} onWithdraw={withdraw} busy={withdrawing !== null} />
          ))}
        </ul>
      )}

      {closedLines.length > 0 && (
        <ul className="text-sm text-secondary">
          {closedLines.map((line) => (
            <li key={line.order_item_id}>
              {line.product_name}: {line.unavailable_reason}
            </li>
          ))}
        </ul>
      )}

      {draft ? (
        <ReturnForm
          orderId={orderId}
          draft={draft}
          onChange={setDraft}
          onCancel={() => setDraft(null)}
          onSent={() => {
            setDraft(null);
            router.refresh();
          }}
        />
      ) : (
        canRequest && (
          <div className="w-48">
            <Button size="md" variant="keyboard" label="Request a return" onClick={() => setDraft(ReturnDraft.start(data.eligibility))} />
          </div>
        )
      )}

      {!canRequest && data.returns.length === 0 && closedLines.length === 0 && (
        <p className="text-sm text-secondary">Once your items are delivered, you can ask to return them here.</p>
      )}
    </section>
  );
};

export default OrderReturns;
