import type { Metadata } from 'next';
import { Poppins } from 'next/font/google';

import NavBar from './components/navbar/NavBar';
import Footer from './components/footer/Footer';

import './globals.css';


//setting google fonts (already integrated in next.js)
const poppins = Poppins({ subsets: ['latin'],
						  weight:['400', '700'] });


export const metadata: Metadata = {
	title: 'My best E-commerce shop',
	description: 'E-commerce app',
};


export default function RootLayout({
  	children,
}: {
  	children: React.ReactNode
}) {
	return (
		<html lang="en">
			<body className={`${poppins.className} text-slate-700`}>
				<div className='flex flex-col min-h-screen'>
					<NavBar/>

						<main className='flex-grow'>
							{children}
						</main>

					<Footer/>
				</div>
				
			</body>
		</html>
	)
};