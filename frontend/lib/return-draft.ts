import type {
  ReturnableLine,
  ReturnEligibility,
  ReturnFault,
  ReturnLineRequest,
  ReturnReason,
  ReturnRequestCreate,
} from "@/types/returns";

/**
 * The limits order-service applies (RETURN_PHOTO_MAX_COUNT / _MAX_BYTES and
 * the formats its sniffer accepts). Checked here only to fail fast; the
 * server checks every photo again from its bytes.
 */
export const RETURN_PHOTO_LIMITS = {
  maxCount: 5,
  maxBytes: 5 * 1024 * 1024,
  types: ["image/jpeg", "image/png", "image/webp"],
} as const;

/** ReturnRequestCreate.description bounds. */
const DESCRIPTION_MIN = 3;
export const DESCRIPTION_MAX = 2000;

/** How each reason reads, and whose fault it is (mirrors contracts/returns.py). */
export const RETURN_REASONS: Readonly<Record<ReturnReason, { label: string; fault: ReturnFault }>> = {
  defective: { label: "It is defective", fault: "seller" },
  damaged: { label: "It arrived damaged", fault: "seller" },
  wrong_item: { label: "I received the wrong item", fault: "seller" },
  misprint: { label: "The print is wrong", fault: "seller" },
  changed_mind: { label: "I changed my mind", fault: "customer" },
  does_not_fit: { label: "It does not fit", fault: "customer" },
};

/** Why a chosen file cannot be attached, or null when it can. */
export const photoProblem = (file: File): string | null => {
  if (!(RETURN_PHOTO_LIMITS.types as readonly string[]).includes(file.type)) {
    return `${file.name} is not a JPEG, PNG or WebP image.`;
  }
  if (file.size > RETURN_PHOTO_LIMITS.maxBytes) {
    return `${file.name} is larger than 5 MB.`;
  }
  return null;
};

/**
 * A return request being filled in, checked by the rules order-service will
 * check it with. Immutable: every change returns a new draft, so it can live
 * in React state as it is.
 *
 * Lines and reason depend on each other: a custom print can only be returned
 * for the seller's fault, so the reasons offered are those every chosen line
 * allows, and choosing a line that does not allow the current reason clears it.
 */
export class ReturnDraft {
  private constructor(
    private readonly eligibility: ReturnEligibility,
    /** Units chosen per order line; a line not chosen is absent. */
    private readonly quantities: ReadonlyMap<string, number>,
    readonly reason: ReturnReason | null,
    readonly description: string,
    readonly photos: readonly File[],
  ) {}

  static start(eligibility: ReturnEligibility): ReturnDraft {
    return new ReturnDraft(eligibility, new Map(), null, "", []);
  }

  /** Lines with at least one unit that can still be returned. */
  get returnableLines(): ReturnableLine[] {
    return this.eligibility.lines.filter((line) => line.returnable_quantity > 0);
  }

  quantityOf(orderItemId: string): number {
    return this.quantities.get(orderItemId) ?? 0;
  }

  /** Sets how many units of a line to return; 0 takes the line out. */
  withQuantity(orderItemId: string, quantity: number): ReturnDraft {
    const line = this.returnableLines.find((entry) => entry.order_item_id === orderItemId);
    if (!line) return this;
    const quantities = new Map(this.quantities);
    const clamped = Math.min(Math.max(Math.trunc(quantity), 0), line.returnable_quantity);
    if (clamped === 0) quantities.delete(orderItemId);
    else quantities.set(orderItemId, clamped);
    const next = new ReturnDraft(this.eligibility, quantities, this.reason, this.description, this.photos);
    // A newly chosen line may not allow the reason picked so far.
    return next.reason && !next.allowedReasons.includes(next.reason) ? next.withReason(null) : next;
  }

  withReason(reason: ReturnReason | null): ReturnDraft {
    return new ReturnDraft(this.eligibility, this.quantities, reason, this.description, this.photos);
  }

  withDescription(description: string): ReturnDraft {
    return new ReturnDraft(this.eligibility, this.quantities, this.reason, description.slice(0, DESCRIPTION_MAX), this.photos);
  }

  /** Adds photos up to the limit; files that cannot be attached are left out by the caller. */
  withPhotosAdded(files: readonly File[]): ReturnDraft {
    const photos = [...this.photos, ...files].slice(0, RETURN_PHOTO_LIMITS.maxCount);
    return new ReturnDraft(this.eligibility, this.quantities, this.reason, this.description, photos);
  }

  withoutPhoto(index: number): ReturnDraft {
    const photos = this.photos.filter((_, position) => position !== index);
    return new ReturnDraft(this.eligibility, this.quantities, this.reason, this.description, photos);
  }

  get chosenLines(): ReturnLineRequest[] {
    return Array.from(this.quantities, ([order_item_id, quantity]) => ({ order_item_id, quantity }));
  }

  /**
   * The reasons every chosen line allows, in the backend's order. Before any
   * line is chosen, every reason some returnable line allows.
   */
  get allowedReasons(): ReturnReason[] {
    const chosen = this.returnableLines.filter((line) => this.quantities.has(line.order_item_id));
    const reasons = Object.keys(RETURN_REASONS) as ReturnReason[];
    if (chosen.length > 0) {
      return reasons.filter((reason) => chosen.every((line) => line.allowed_reasons.includes(reason)));
    }
    return reasons.filter((reason) => this.returnableLines.some((line) => line.allowed_reasons.includes(reason)));
  }

  get needsPhoto(): boolean {
    return this.reason !== null && this.eligibility.photo_required_for.includes(this.reason);
  }

  /** What still stands in the way of sending, in the order the form asks for it. */
  get problems(): string[] {
    const problems: string[] = [];
    if (this.quantities.size === 0) problems.push("Choose at least one item to return.");
    if (this.reason === null) problems.push("Choose a reason.");
    if (this.description.trim().length < DESCRIPTION_MIN) problems.push("Tell us briefly what happened.");
    if (this.needsPhoto && this.photos.length === 0) problems.push("Add at least one photo showing the problem.");
    return problems;
  }

  /** The request to send; only call it when `problems` is empty. */
  toRequest(): ReturnRequestCreate {
    if (this.reason === null || this.problems.length > 0) {
      throw new Error("the return request is not complete");
    }
    return { lines: this.chosenLines, reason: this.reason, description: this.description.trim() };
  }
}
