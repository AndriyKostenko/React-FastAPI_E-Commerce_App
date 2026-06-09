import Link from "next/link";
import CartCount from "./CartCount";
import UserMenu from "./UserMenu";
import { sessionManagaer } from "@/actions/getCurrentUser";
import SearchBar from "./SearchBar";
import { Suspense } from "react";

const NavBar = async () => {
    // getting current user from the server session
    const currentUser = await sessionManagaer.getCurrentUser();
    const currentUserRole = await sessionManagaer.getCurrentUserRole();

    return (
        <header className="w-full z-50 px-margin-desktop py-6">
            <nav className="flex justify-between items-center max-w-container-max mx-auto">
                {/* Left: Brand + Nav Links */}
                <div className="flex items-center gap-12">
                    <Link
                        href="/"
                        className="font-display-lg text-headline-xl tracking-tighter text-primary select-none hover:opacity-80 transition-opacity"
                    >
                        AIGEN
                    </Link>

                    <div className="hidden xl:flex items-center gap-8">
                        <Link
                            href="/"
                            className="font-label-bold text-label-bold text-primary border-b-2 border-primary pb-1 transition-all"
                        >
                            Home
                        </Link>
                        <Link
                            href="/"
                            className="font-label-bold text-label-bold text-secondary hover:text-primary transition-colors"
                        >
                            Create Design
                        </Link>
                        <Link
                            href="/"
                            className="font-label-bold text-label-bold text-secondary hover:text-primary transition-colors"
                        >
                            Shop
                        </Link>
                        <Link
                            href="/"
                            className="font-label-bold text-label-bold text-secondary hover:text-primary transition-colors"
                        >
                            Best Sellers
                        </Link>
                    </div>
                </div>

                {/* Center: Search */}
                <div className="hidden lg:flex items-center bg-white/50 backdrop-blur rounded-full px-4 py-2 gap-3 border border-white/20">
                    <Suspense fallback={null}>
                        <SearchBar />
                    </Suspense>
                </div>

                {/* Right: Cart + User */}
                <div className="flex items-center gap-2">
                    <div className="bg-white/50 backdrop-blur p-3 rounded-full border border-white/20 hover:bg-white transition-all cursor-pointer">
                        <CartCount />
                    </div>
                    <UserMenu
                        currentUser={currentUser}
                        currentUserRole={currentUserRole}
                    />
                </div>
            </nav>
        </header>
    );
};

export default NavBar;
