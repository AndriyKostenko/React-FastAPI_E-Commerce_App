import type { Metadata } from "next";
import LegalPage, { ContactEmail, PolicyLink, type LegalSection } from "@/components/legal/LegalPage";

export const metadata: Metadata = {
    title: "Terms of use | AIGEN",
    description: "The terms that apply when you use the AIGEN store and buy from it.",
};

const sections: LegalSection[] = [
    {
        heading: "Who can buy",
        body: (
            <p>
                You must be at least the age of majority where you live (18 in Alberta) to create an
                account or place an order, and orders must ship to an address in Canada. If you
                create an account, keep your password private: you are responsible for what happens
                under your account.
            </p>
        ),
    },
    {
        heading: "Orders and prices",
        body: (
            <>
                <p>
                    Prices are in Canadian dollars. The total at checkout, including shipping and any
                    tax that applies, is the amount you pay. Your order is a request to buy; it is
                    accepted when we confirm it.
                </p>
                <p>
                    We may cancel an order, with a full refund or a release of the hold on your card,
                    if an item is unavailable, a price was shown in error, or we suspect fraud.
                </p>
                <p>
                    Product photos and design previews show what to expect, but colours, print
                    placement and size can vary slightly from what your screen shows.
                </p>
            </>
        ),
    },
    {
        heading: "Payment",
        body: (
            <p>
                Payments are processed by Stripe. When you order, we place a hold on your card and
                charge it when the order is confirmed, as described in our{" "}
                <PolicyLink to="shipping">shipping policy</PolicyLink>.
            </p>
        ),
    },
    {
        heading: "Designs you create",
        body: (
            <>
                <p>
                    Our design tool uses artificial intelligence to generate images from the text you
                    write. You are responsible for your prompts and for what you ask us to print. Do
                    not ask for designs that:
                </p>
                <ul className="list-disc pl-6 flex flex-col gap-1">
                    <li>copy someone else&apos;s trademark, logo, character or artwork, or a real person&apos;s likeness without their permission;</li>
                    <li>are hateful, harassing, sexually explicit or violent, or promote illegal activity.</li>
                </ul>
                <p>
                    We may refuse to print, or cancel and refund, any order whose design we believe
                    breaks these rules.
                </p>
                <p>
                    You keep whatever rights you have in your prompts. You give us permission to use
                    your prompts and the generated images to make, show you and ship your order, and
                    to keep them with your order records. Generated images may resemble images made
                    for other people, and may not be protected by copyright, so we cannot promise a
                    design is unique to you.
                </p>
            </>
        ),
    },
    {
        heading: "Returns and refunds",
        body: (
            <p>
                Returns, refunds and cancellations follow our{" "}
                <PolicyLink to="returns">returns policy</PolicyLink>.
            </p>
        ),
    },
    {
        heading: "Using the store",
        body: (
            <p>
                Do not misuse the store, for example by trying to break its security, overload it,
                scrape it in bulk or use someone else&apos;s account. We may suspend or close an
                account that does. The store&apos;s content, apart from your own designs and
                reviews, belongs to us or our licensors.
            </p>
        ),
    },
    {
        heading: "Reviews",
        body: (
            <p>
                Reviews must be honest and about the product. By posting one, you let us show it in
                the store, including on the home page. We may remove reviews that are abusive,
                off-topic or misleading.
            </p>
        ),
    },
    {
        heading: "Liability",
        body: (
            <p>
                To the extent the law allows, our total liability for any claim about an order is
                limited to the amount you paid for that order, and we are not liable for indirect or
                consequential losses. Nothing in these terms limits rights you have under consumer
                protection law that cannot be waived.
            </p>
        ),
    },
    {
        heading: "Governing law",
        body: (
            <p>
                These terms are governed by the laws of Alberta and the federal laws of Canada that
                apply there.
            </p>
        ),
    },
    {
        heading: "Changes to these terms",
        body: (
            <p>
                We may update these terms. The version shown here when you place an order applies to
                that order. Questions about these terms go to <ContactEmail />.
            </p>
        ),
    },
];

export default function TermsPage() {
    return (
        <LegalPage
            title="Terms of use"
            intro={
                <>
                    <p>
                        These terms apply when you use the AIGEN store and buy from it. By using the
                        store or placing an order, you agree to them.
                    </p>
                    <p>
                        How we handle your personal information is explained in our{" "}
                        <PolicyLink to="privacy">privacy policy</PolicyLink>.
                    </p>
                </>
            }
            sections={sections}
        />
    );
}
