"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useState, type MouseEvent } from "react";
import { slugForTab } from "@/utils/collectionTabs";

type HeaderTab = "home" | "create-design" | "shop" | "best-sellers";

const links: { href: string; label: string; tab: HeaderTab }[] = [
    { href: "/", label: "Home", tab: "home" },
    { href: "/#create-design", label: "Create Design", tab: "create-design" },
    { href: "/#shop", label: "Shop", tab: "shop" },
    {
        href: `/?collection=${slugForTab("Best Sellers")}#shop`,
        label: "Best Sellers",
        tab: "best-sellers",
    },
];

// Read only by the shop section in the browser; the server render ignores it.
const CLIENT_ONLY_PARAM = "collection";

/** Whether two queries are equal once the client-only parameter is set aside. */
const sameServerQuery = (left: URLSearchParams, right: URLSearchParams): boolean => {
    const strip = (params: URLSearchParams): string => {
        const copy = new URLSearchParams(params);
        copy.delete(CLIENT_ONLY_PARAM);
        copy.sort();
        return copy.toString();
    };
    return strip(left) === strip(right);
};

/**
 * Links within the page already showing. The router does nothing for the
 * same URL, and does not scroll when only `?collection=` changes under the same
 * hash, so either way the link looked dead after scrolling away. When the
 * server would render the same page, update the URL here (the shop section
 * reads the tab from it) and scroll to the link's section, or the top.
 */
const navigateWithinPage = (
    event: MouseEvent<HTMLAnchorElement>,
    href: string,
    // pushState fires no hashchange, so the caller is told the new hash.
    onHashChange: (hash: string) => void,
): void => {
    const target = new URL(href, window.location.href);
    const here = new URL(window.location.href);
    if (target.pathname !== here.pathname || !sameServerQuery(target.searchParams, here.searchParams)) {
        return;
    }
    event.preventDefault();
    if (target.href !== here.href) {
        window.history.pushState(null, "", target.href);
        onHashChange(target.hash);
    }
    const section = target.hash ? document.getElementById(target.hash.slice(1)) : null;
    if (section) section.scrollIntoView({ behavior: "smooth" });
    else window.scrollTo({ top: 0, behavior: "smooth" });
};

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
        if (searchParams.get("collection") === slugForTab("Best Sellers")) {
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
                    onClick={(event) => navigateWithinPage(event, href, setHash)}
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
