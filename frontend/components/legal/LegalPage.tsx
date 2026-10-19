import type { ReactNode } from "react";
import Link from "next/link";
import Container from "@/components/ui/Container";
import {
  BUSINESS,
  LEGAL_PAGES_UPDATED,
  businessAddressLine,
} from "@/lib/business";

export interface LegalSection {
  heading: string;
  body: ReactNode;
}

interface LegalPageProps {
  title: string;
  intro: ReactNode;
  sections: LegalSection[];
}

/** The pages a policy links to, so every one can point at the others. */
export const POLICY_LINKS = {
  terms: "/terms",
  privacy: "/privacy",
  returns: "/returns",
  shipping: "/shipping",
} as const;

export const ContactEmail = () => (
  <a href={`mailto:${BUSINESS.email}`} className="underline hover:text-primary">
    {BUSINESS.email}
  </a>
);

export const PolicyLink = ({
  to,
  children,
}: {
  to: keyof typeof POLICY_LINKS;
  children: ReactNode;
}) => (
  <Link href={POLICY_LINKS[to]} className="underline hover:text-primary">
    {children}
  </Link>
);

/**
 * One store policy: a title, a short intro, numbered sections and the
 * contact block every policy ends with.
 */
const LegalPage = ({ title, intro, sections }: LegalPageProps) => (
  <div className="py-8">
    <Container>
      <article className="glass-card p-6 md:p-10 max-w-3xl mx-auto flex flex-col gap-8 text-secondary leading-relaxed">
        <header className="flex flex-col gap-2">
          <h1 className="font-bold text-3xl text-primary">{title}</h1>
          <p className="text-sm">Last updated: {LEGAL_PAGES_UPDATED}</p>
          <div className="pt-2 flex flex-col gap-3">{intro}</div>
        </header>

        {sections.map((section, index) => (
          <section key={section.heading} className="flex flex-col gap-3">
            <h2 className="font-bold text-xl text-primary">
              {index + 1}. {section.heading}
            </h2>
            {section.body}
          </section>
        ))}

        <footer className="border-t border-white/30 pt-6 flex flex-col gap-1">
          <h2 className="font-bold text-xl text-primary">Contact us</h2>
          <p>{BUSINESS.name}</p>
          <p>{businessAddressLine()}</p>
          <p>
            Email: <ContactEmail />
          </p>
        </footer>
      </article>
    </Container>
  </div>
);

export default LegalPage;
