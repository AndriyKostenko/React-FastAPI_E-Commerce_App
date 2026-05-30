import type { Metadata } from 'next';
import { Hanken_Grotesk, Inter } from 'next/font/google';

import NavBar from '@/components/1. Header/NavBar';
import Footer from '@/components/6. Footer/Footer';

import './globals.css';
import CartProvider from '@/providers/CartProvider';
import { Toaster } from 'react-hot-toast';



//setting google fonts
const hankenGrotesk = Hanken_Grotesk({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700', '800'],
  variable: '--font-hanken-grotesk',
});

const inter = Inter({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-inter',
});
						  
export const metadata: Metadata = {
	title: 'AIGEN | Generative Luxury Streetwear',
	description: 'Pioneering the intersection of artificial intelligence and premium streetwear.',
};
export const dynamic = "force-dynamic";





export default async function RootLayout({children}: {children: React.ReactNode}) {
	return (
		<html lang="en" suppressHydrationWarning>
			<body className={`${hankenGrotesk.variable} ${inter.variable} font-body-md text-on-surface overflow-x-hidden gradient-bg p-4 md:p-8`}>
				<Toaster toastOptions={{
							style: {
								background: 'rgb(51 65 85)', 
								color: '#fff'
							}
						}}>
				</Toaster>

				<CartProvider>
					<div className="max-w-[1600px] mx-auto space-y-8">
						<div className="glass-card shadow-2xl overflow-hidden min-h-screen border-none flex flex-col">
							<NavBar/>

							<main className="flex-grow p-4 md:p-8 space-y-8">
								{children}
							</main>

							<Footer/>
						</div>
					</div>
				</CartProvider>

				
			</body>
		</html>
	)
};
