import type { Metadata } from "next";
import LegalPage, { ContactEmail, PolicyLink, type LegalSection } from "@/components/legal/LegalPage";

export const metadata: Metadata = {
    title: "Shipping | AIGEN",
    description: "Where we ship, what it costs and how long it takes.",
};

const sections: LegalSection[] = [
    {
        heading: "Where we ship",
        body: (
            <p>
                We ship to addresses in Canada only. Checkout accepts Canadian shipping addresses,
                and all prices are in Canadian dollars (CAD).
            </p>
        ),
    },
    {
        heading: "Where your order comes from",
        body: (
            <>
                <p>
                    <strong className="text-primary">Custom-designed T-shirts</strong> are printed
                    to order by us and shipped from within Canada.
                </p>
                <p>
                    <strong className="text-primary">Other catalogue items</strong> are made and
                    shipped by our supplier, from its warehouses in China.
                </p>
                <p>
                    An order with both kinds of item may arrive in more than one parcel.
                </p>
            </>
        ),
    },
    {
        heading: "Cost and delivery time",
        body: (
            <>
                <p>
                    Shipping is charged per order, and you see the cost before you pay. For items
                    from our supplier, checkout lists the available shipping options with each
                    one&apos;s price and estimated delivery time in days.
                </p>
                <p>
                    Delivery times are estimates from the carrier and are not guaranteed. Customs
                    checks and carrier delays can make a parcel arrive later.
                </p>
            </>
        ),
    },
    {
        heading: "When we charge your card",
        body: (
            <p>
                When you place an order, we put a hold on your card for the total. We charge it once
                your order is confirmed: straight away when we make or stock every item ourselves,
                or once our supplier has accepted the order when it includes supplier items. If we
                cannot fulfil your order, we release the hold or refund you in full.
            </p>
        ),
    },
    {
        heading: "Tracking",
        body: (
            <p>
                We email you when your order ships, with a tracking number when the carrier provides
                one. You can also follow each item&apos;s progress on its order page under Your
                orders.
            </p>
        ),
    },
    {
        heading: "Problems with delivery",
        body: (
            <>
                <p>
                    Please check your shipping address before you pay. We cannot redirect a parcel
                    once it has shipped.
                </p>
                <p>
                    If your parcel has not arrived well after its estimated delivery time, or it
                    arrived damaged, email us at <ContactEmail /> with your order number. For
                    damaged or wrong items, you can also ask for a return from the order page. See
                    our <PolicyLink to="returns">returns policy</PolicyLink>.
                </p>
            </>
        ),
    },
];

export default function ShippingPage() {
    return (
        <LegalPage
            title="Shipping"
            intro={<p>Where we ship, what it costs and how long it takes.</p>}
            sections={sections}
        />
    );
}
