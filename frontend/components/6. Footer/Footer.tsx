"use client";

import Link from "next/link";
import Container from "@/components/ui/Container";
import { useState } from "react";
import { toast } from "react-hot-toast";
import { MdArrowForward } from "react-icons/md";

const Footer = () => {
    const [email, setEmail] = useState("");

    const handleNewsletterSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!email.trim()) return;
        toast.success("You're subscribed! Welcome to the studio.");
        setEmail("");
    };

    return (
        <footer className="p-8 md:p-12 bg-black/5 border-t border-white/20 mt-auto">
            <Container>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-12 max-w-container-max mx-auto mb-12">

                    {/* Brand Info */}
                    <div className="space-y-6">
                        <Link href="/" className="font-display-lg text-headline-xl font-extrabold text-primary tracking-tighter select-none">
                            AIGEN
                        </Link>
                        <p className="font-body-md text-secondary text-sm max-w-[200px] leading-relaxed">
                            Pioneering the intersection of artificial intelligence and premium streetwear.
                        </p>
                    </div>

                    {/* Shop Links */}
                    <div className="space-y-4">
                        <h4 className="font-label-bold text-xs font-semibold text-primary uppercase tracking-[0.15em]">COLLECTIONS</h4>
                        <nav className="flex flex-col gap-2">
                            <Link href="#" className="font-body-md text-sm text-secondary hover:text-primary transition-all">New Arrivals</Link>
                            <Link href="#" className="font-body-md text-sm text-secondary hover:text-primary transition-all">Best Sellers</Link>
                            <Link href="#" className="font-body-md text-sm text-secondary hover:text-primary transition-all">Limited Edition</Link>
                        </nav>
                    </div>

                    {/* Company Links */}
                    <div className="space-y-4">
                        <h4 className="font-label-bold text-xs font-semibold text-primary uppercase tracking-[0.15em]">COMPANY</h4>
                        <nav className="flex flex-col gap-2">
                            <Link href="#" className="font-body-md text-sm text-secondary hover:text-primary transition-all">About Studio</Link>
                            <Link href="#" className="font-body-md text-sm text-secondary hover:text-primary transition-all">Sustainability</Link>
                            <Link href="#" className="font-body-md text-sm text-secondary hover:text-primary transition-all">Careers</Link>
                        </nav>
                    </div>

                    {/* Newsletter */}
                    <div className="space-y-4">
                        <h4 className="font-label-bold text-xs font-semibold text-primary uppercase tracking-[0.15em]">STAY UPDATED</h4>
                        <form onSubmit={handleNewsletterSubmit} className="flex bg-white/60 backdrop-blur rounded-full p-1 border border-white/40">
                            <input
                                type="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                placeholder="Email address"
                                className="bg-transparent border-none focus:ring-0 focus:outline-none px-4 flex-grow text-sm font-body-md text-primary placeholder:text-secondary"
                            />
                            <button
                                type="submit"
                                className="bg-black text-white p-2 rounded-full hover:bg-neutral-800 transition-all active:scale-95 flex items-center justify-center"
                            >
                                <MdArrowForward size={20} />
                            </button>
                        </form>
                    </div>

                </div>

                {/* Bottom Bar */}
                <div className="flex flex-col md:flex-row justify-between items-center pt-8 border-t border-white/20 gap-4">
                    <p className="font-body-md text-sm text-secondary">
                        &copy; {new Date().getFullYear()} AIGEN Studio. High Resolution Art.
                    </p>
                    <div className="flex gap-8">
                        <Link href="#" className="text-sm text-secondary hover:text-primary transition-all">Instagram</Link>
                        <Link href="#" className="text-sm text-secondary hover:text-primary transition-all">Twitter</Link>
                        <Link href="#" className="text-sm text-secondary hover:text-primary transition-all">Terms of Use</Link>
                    </div>
                </div>
            </Container>
        </footer>
    );
}

export default Footer;