import type { Metadata } from "next";
import LegalPage, {
  ContactEmail,
  PolicyLink,
  type LegalSection,
} from "@/components/legal/LegalPage";
import { RETURN_REASONS } from "@/lib/return-draft";

export const metadata: Metadata = {
  title: "Returns & refunds | AIGEN",
  description: "How to return an item, what we refund and when.",
};

// The labels the return form shows, so the policy names reasons exactly as
// the customer will pick them.
const reasonLabels = (fault: "seller" | "customer"): string[] =>
  Object.values(RETURN_REASONS)
    .filter((reason) => reason.fault === fault)
    .map((reason) => `“${reason.label}”`);

const sections: LegalSection[] = [
  {
    heading: "How long you have",
    body: (
      <p>
        You can ask to return an item for up to 30 days after it was delivered.
        Each item counts separately: if you bought three of something, you can
        return one, two or all three, and each can be returned once.
      </p>
    ),
  },
  {
    heading: "How to ask for a return",
    body: (
      <ol className="list-decimal pl-6 flex flex-col gap-1">
        <li>Sign in and open the order from Your orders.</li>
        <li>
          Choose Request a return, pick the items and how many, and tell us why.
        </li>
        <li>
          If something is wrong with the item, add at least one photo that shows
          the problem.
        </li>
        <li>We review every request and email you our decision.</li>
      </ol>
    ),
  },
  {
    heading: "If something is wrong with your item",
    body: (
      <>
        <p>
          This covers the reasons {reasonLabels("seller").join(", ")}. We need a
          photo of the problem.
        </p>
        <p>
          Once we approve it, we refund the item and the shipping you paid for
          the order (shipping is refunded once per order). In most cases you do
          not need to send the item back. If we do need it back, we email you
          the return address.
        </p>
      </>
    ),
  },
  {
    heading: "If you changed your mind",
    body: (
      <>
        <p>This covers the reasons {reasonLabels("customer").join(" and ")}.</p>
        <p>
          Once we approve the return, we email you the address to send the item
          to. You pay for return shipping, and the original shipping is not
          refunded. We refund the item once it reaches us unused and in its
          original condition. There is no restocking fee.
        </p>
        <p>
          <strong className="text-primary">Custom-designed T-shirts</strong> are
          made for you alone, so they can be returned only if something is wrong
          with them, not for a change of mind or fit.
        </p>
      </>
    ),
  },
  {
    heading: "Changing your mind before we decide",
    body: (
      <p>
        You can withdraw a return request from the order page until we have
        reviewed it. The items then become available to return again.
      </p>
    ),
  },
  {
    heading: "Refunds",
    body: (
      <>
        <p>
          Refunds go back to the card or payment method you used, and we email
          you when a refund is issued. Your bank usually shows it within 5 to 10
          business days.
        </p>
        <p>
          We do not offer exchanges. To get a different size or colour, return
          the item and place a new order.
        </p>
      </>
    ),
  },
  {
    heading: "Cancelling an order",
    body: (
      <p>
        To cancel, email us at <ContactEmail /> with your order number as soon
        as possible. We cancel and refund in full any order that has not yet
        been printed or sent to our supplier. After that, the return rules above
        apply.
      </p>
    ),
  },
  {
    heading: "Your rights",
    body: (
      <p>
        This policy adds to, and does not limit, any rights you have under
        consumer protection law. See also our{" "}
        <PolicyLink to="shipping">shipping policy</PolicyLink> and{" "}
        <PolicyLink to="terms">terms of use</PolicyLink>.
      </p>
    ),
  },
];

export default function ReturnsPage() {
  return (
    <LegalPage
      title="Returns & refunds"
      intro={<p>Here is how returns work at AIGEN, what we refund and when.</p>}
      sections={sections}
    />
  );
}
