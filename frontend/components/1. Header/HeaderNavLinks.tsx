"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

type HeaderTab = "home" | "create-design" | "shop" | "best-sellers";

const links: { href: string; label: string; tab: HeaderTab }[] = [
    { href: "/", label: "Home", tab: "home" },
    { href: "/#create-design", label: "Create Design", tab: "create-design" },
    { href: "/#shop", label: "Shop", tab: "shop" },
    {
        href: "/?collection=trending#shop",
        label: "Best Sellers",
        tab: "best-sellers",
    },
];

const HeaderNavLinks = () => {
    const pathname = usePathname();
    const searchParams = useSearchParams();
    const [hash, setHash] = useState("");

    useEffect(() => {
        const updateHash = () => setHash(window.location.hash);

        updateHash();
        window.addEventListener("hashchange", updateHash);
        return () => window.removeEventListener("hashchange", updateHash);
    }, [pathname, searchParams]);

    let activeTab: HeaderTab | null = null;
    if (pathname === "/") {
        if (searchParams.get("collection") === "trending") {
            activeTab = "best-sellers";
        } else if (hash === "#create-design") {
            activeTab = "create-design";
        } else if (hash === "#shop") {
            activeTab = "shop";
        } else {
            activeTab = "home";
        }
    }

    return (
        <div className="hidden xl:flex items-center gap-8">
            {links.map(({ href, label, tab }) => (
                <Link
                    key={tab}
                    href={href}
                    aria-current={activeTab === tab ? "page" : undefined}
                    className={`font-label-bold text-label-bold border-b-2 pb-1 transition-all ${
                        activeTab === tab
                            ? "border-primary text-primary"
                            : "border-transparent text-secondary hover:text-primary"
                    }`}
                >
                    {label}
                </Link>
            ))}
        </div>
    );
};

export default HeaderNavLinks;
