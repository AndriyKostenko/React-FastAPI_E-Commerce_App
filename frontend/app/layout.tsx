import type { Metadata } from 'next';
import { Poppins } from 'next/font/google';

import NavBar from './components/navbar/NavBar';
import Footer from './components/footer/Footer';

import './globals.css';
import CartProvider from '@/providers/CartProvider';


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
				{/* wrapping all components into CartProvider for letting all other components acces the current 'value' defined in CartContextProvier  */}
				{/* all of them now will be passes as 'children' to CartProvider component*/}
				<CartProvider>

					<div className='flex flex-col min-h-screen'>
						<NavBar/>

							<main className='flex-grow'>
								{children}
							</main>

						<Footer/>
					</div>

				</CartProvider>

				
			</body>
		</html>
	)
};
