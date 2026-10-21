import Link from "next/link";
import Container from "@/components/ui/Container";
import { BUSINESS, socialLinks } from "@/lib/business";

interface FooterLink {
  label: string;
  href: string;
}

interface FooterColumn {
  title: string;
  links: FooterLink[];
}

// Every link goes somewhere real: a page, a section of the home page or the
// contact inbox. Add a column entry only once its page exists.
const COLUMNS: FooterColumn[] = [
  {
    title: "SHOP",
    links: [
      { label: "Shop all", href: "/#shop" },
      { label: "Design your own", href: "/#create-design" },
      { label: "Wishlist", href: "/wishlist" },
      { label: "Your orders", href: "/orders" },
    ],
  },
  {
    title: "HELP",
    links: [
      { label: "Shipping", href: "/shipping" },
      { label: "Returns & refunds", href: "/returns" },
      { label: "Contact us", href: `mailto:${BUSINESS.email}` },
    ],
  },
  {
    title: "LEGAL",
    links: [
      { label: "Terms of use", href: "/terms" },
      { label: "Privacy policy", href: "/privacy" },
    ],
  },
];

const Footer = () => {
  const socials = socialLinks();

  return (
    <footer className="p-8 md:p-12 bg-black/5 border-t border-white/20 mt-auto">
      <Container>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-12 max-w-container-max mx-auto mb-12">
          {/* Brand Info */}
          <div className="space-y-6">
            <Link
              href="/"
              className="font-display-lg text-headline-xl font-extrabold text-primary tracking-tighter select-none"
            >
              {BUSINESS.name}
            </Link>
            <p className="font-body-md text-secondary text-sm max-w-[200px] leading-relaxed">
              Pioneering the intersection of artificial intelligence and premium
              streetwear.
            </p>
          </div>

          {COLUMNS.map((column) => (
            <div key={column.title} className="space-y-4">
              <h2 className="font-label-bold text-xs font-semibold text-primary uppercase tracking-[0.15em]">
                {column.title}
              </h2>
              <nav className="flex flex-col gap-2">
                {column.links.map((link) => (
                  <Link
                    key={link.label}
                    href={link.href}
                    className="font-body-md text-sm text-secondary hover:text-primary transition-all"
                  >
                    {link.label}
                  </Link>
                ))}
              </nav>
            </div>
          ))}
        </div>

        {/* Bottom Bar */}
        <div className="flex flex-col md:flex-row justify-between items-center pt-8 border-t border-white/20 gap-4">
          <p className="font-body-md text-sm text-secondary">
            &copy; {new Date().getFullYear()} {BUSINESS.name}. All rights
            reserved.
          </p>
          {socials.length > 0 && (
            <div className="flex gap-8">
              {socials.map((social) => (
                <a
                  key={social.label}
                  href={social.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-secondary hover:text-primary transition-all"
                >
                  {social.label}
                </a>
              ))}
            </div>
          )}
        </div>
      </Container>
    </footer>
  );
};

export default Footer;
