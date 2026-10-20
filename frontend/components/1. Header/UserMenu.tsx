"use client";

import { UserMenuProps } from "@/types/navbar";
import Avatar from "@/components/ui/Avatar";
import { useCallback, useState } from "react";
import MenuItem from "./MenuItem";
import Link from "next/link";
import BackDrop from "./BackDrop";
import { signOut } from "@/lib/sign-out";
import { clearUserScopedStorage } from "@/utils/client-storage";

const UserMenu: React.FC<UserMenuProps> = ({ currentUser }) => {
    const [isOpen, setIsOpen] = useState(false);

    const toggleOpen = useCallback(() => {
        setIsOpen((prev) => !prev);
    }, []);

    return (
        <>
            <div className="relative z-30">
                <div
                    onClick={toggleOpen}
                    className="bg-white/50 backdrop-blur pl-4 pr-2 py-2 rounded-full border border-white/20 hover:bg-white transition-all flex items-center gap-2 cursor-pointer"
                >
                    <span className="font-label-bold text-sm text-primary hidden sm:block">
                        Account
                    </span>
                    <div className="w-8 h-8 rounded-full bg-primary-container overflow-hidden">
                        <Avatar src={currentUser?.image} size={32} />
                    </div>
                </div>
                {isOpen && (
                    <div className="absolute rounded-2xl border border-white/30 luxury-shadow w-[170px] bg-white/90 backdrop-blur-md overflow-hidden right-0 top-14 text-sm flex flex-col cursor-pointer z-50">
                        {currentUser !== undefined && currentUser !== null ? (
                            <div>
                                <Link href="/account">
                                    <MenuItem onClick={toggleOpen}>
                                        Your Account
                                    </MenuItem>
                                </Link>
                                <Link href="/orders">
                                    <MenuItem onClick={toggleOpen}>
                                        Your Orders
                                    </MenuItem>
                                </Link>
                                <Link href="/wishlist">
                                    <MenuItem onClick={toggleOpen}>
                                        Your Wishlist
                                    </MenuItem>
                                </Link>
                                <MenuItem
                                    onClick={() => {
                                        toggleOpen();
                                        clearUserScopedStorage();
                                        void signOut();
                                    }}
                                >
                                    Logout
                                </MenuItem>
                            </div>
                        ) : (
                            <div>
                                <Link href="/login">
                                    <MenuItem onClick={toggleOpen}>
                                        Login
                                    </MenuItem>
                                </Link>
                                <Link href="/register">
                                    <MenuItem onClick={toggleOpen}>
                                        Register
                                    </MenuItem>
                                </Link>
                            </div>
                        )}
                    </div>
                )}
            </div>
            {isOpen ? <BackDrop onClick={toggleOpen} /> : null}
        </>
    );
};

export default UserMenu;
