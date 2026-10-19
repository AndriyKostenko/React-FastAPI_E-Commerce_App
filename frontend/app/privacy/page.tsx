import type { Metadata } from "next";
import LegalPage, {
  ContactEmail,
  type LegalSection,
} from "@/components/legal/LegalPage";

export const metadata: Metadata = {
  title: "Privacy policy | AIGEN",
  description:
    "What personal information AIGEN collects, why, who we share it with and your choices.",
};

const sections: LegalSection[] = [
  {
    heading: "What we collect",
    body: (
      <ul className="list-disc pl-6 flex flex-col gap-1">
        <li>
          <strong className="text-primary">Account details:</strong> your name,
          email address and password (stored only as a one-way hash), and, if
          you add them, your phone number and profile picture. If you sign in
          with Google, we receive your name, email address and profile picture
          from Google.
        </li>
        <li>
          <strong className="text-primary">Addresses:</strong> the shipping
          addresses you enter at checkout or save to your address book.
        </li>
        <li>
          <strong className="text-primary">Orders:</strong> what you bought,
          prices, delivery status and tracking numbers.
        </li>
        <li>
          <strong className="text-primary">Payments:</strong> handled by Stripe.
          We never see or store your full card number; we keep only the
          payment&apos;s status and amounts.
        </li>
        <li>
          <strong className="text-primary">Designs:</strong> the text prompts
          you write and the images generated from them.
        </li>
        <li>
          <strong className="text-primary">Returns and reviews:</strong> the
          reasons, descriptions and photos you send with a return request, and
          the reviews you post.
        </li>
        <li>
          <strong className="text-primary">Technical data:</strong> your IP
          address and the requests your browser makes, which we use to keep the
          store secure and to limit abuse.
        </li>
      </ul>
    ),
  },
  {
    heading: "Why we use it",
    body: (
      <ul className="list-disc pl-6 flex flex-col gap-1">
        <li>To run your account and sign you in.</li>
        <li>To take payment for, make, ship and track your orders.</li>
        <li>To generate the designs you ask for.</li>
        <li>To handle returns, refunds and your questions.</li>
        <li>
          To send emails about your account and orders, such as confirmations,
          shipping updates and refunds.
        </li>
        <li>
          To prevent fraud and abuse, and to keep records the law requires.
        </li>
      </ul>
    ),
  },
  {
    heading: "What we do not do",
    body: (
      <p>
        We do not sell your personal information. We do not send marketing
        emails, and we do not use advertising or analytics trackers.
      </p>
    ),
  },
  {
    heading: "Who we share it with",
    body: (
      <>
        <p>We share only what each service needs to do its job for us:</p>
        <ul className="list-disc pl-6 flex flex-col gap-1">
          <li>
            <strong className="text-primary">Stripe</strong> processes your
            payment.
          </li>
          <li>
            <strong className="text-primary">CJ Dropshipping</strong>, our
            supplier, receives your name, shipping address and phone number to
            make and ship supplier items. It is based in China, so this
            information is processed there.
          </li>
          <li>
            <strong className="text-primary">Shipping carriers</strong> receive
            what they need to deliver your parcel.
          </li>
          <li>
            <strong className="text-primary">OpenRouter</strong> and the AI
            model provider it routes to receive your design prompts to generate
            images. We do not send them your name or email address.
          </li>
          <li>
            <strong className="text-primary">Google</strong> signs you in, if
            you choose to sign in with Google.
          </li>
          <li>
            <strong className="text-primary">Our email provider</strong>{" "}
            delivers the emails we send you.
          </li>
          <li>
            <strong className="text-primary">Amazon Web Services</strong> hosts
            our store and its data.
          </li>
        </ul>
        <p>
          Some of these services are outside Canada, and information they hold
          may be subject to the laws of those countries, including access by
          their authorities. We may also disclose information when the law
          requires it.
        </p>
      </>
    ),
  },
  {
    heading: "Where it is stored and for how long",
    body: (
      <>
        <p>
          Our store and its database run on Amazon Web Services servers in
          Canada (Montréal region).
        </p>
        <p>
          We keep your account information until you delete your account.
          Deleting it from your account page removes your profile, saved
          addresses and profile picture. We keep order, payment and return
          records, including the designs printed for an order, for as long as
          tax and accounting law requires, and we keep records needed to resolve
          a dispute until it is resolved.
        </p>
      </>
    ),
  },
  {
    heading: "Cookies and browser storage",
    body: (
      <p>
        We use only the cookies needed to keep you signed in and to secure your
        session. Your browser&apos;s local storage holds your cart and checkout
        progress, so they survive a page reload. We use no advertising or
        analytics cookies.
      </p>
    ),
  },
  {
    heading: "Your choices and rights",
    body: (
      <>
        <p>
          You can see and correct your profile and addresses on your account
          page, and delete your account there at any time. You can also ask us
          for a copy of the personal information we hold about you, ask us to
          correct it, or withdraw your consent to a use of it. Some withdrawals
          mean we can no longer serve you, for example by fulfilling an order.
          Email us at <ContactEmail />, and we will reply within 30 days.
        </p>
        <p>
          If you are not satisfied with our answer, you can complain to the
          Office of the Information and Privacy Commissioner of Alberta or the
          Office of the Privacy Commissioner of Canada.
        </p>
      </>
    ),
  },
  {
    heading: "Security",
    body: (
      <p>
        We protect your information with encrypted connections, hashed passwords
        and access limited to the systems that need it. No system is perfectly
        secure; if a breach puts you at real risk of significant harm, we will
        tell you and the authorities as the law requires.
      </p>
    ),
  },
  {
    heading: "Changes to this policy",
    body: (
      <p>
        We will post any change on this page and update the date at the top. If
        a change is significant, we will also email account holders.
      </p>
    ),
  },
];

export default function PrivacyPage() {
  return (
    <LegalPage
      title="Privacy policy"
      intro={
        <p>
          AIGEN is responsible for the personal information it collects through
          this store. This policy explains what we collect, why, who we share it
          with and the choices you have. Questions go to our privacy contact at{" "}
          <ContactEmail />.
        </p>
      }
      sections={sections}
    />
  );
}
