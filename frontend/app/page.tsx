//import { products } from "@/utils/products";
import Container  from "./components/Container";
import HomeBanner from "./components/banner/HomeBanner";
import ProductCard from "./components/products/ProductCard";
import NullData from "./components/NullData";
import fetchProductsFromBackend from "../actions/getProducts";


// by default it's server component which will be rendered on t he server firsts
export default async function Home() {

	const products = await fetchProductsFromBackend()
	
	if (!products) {
		return <NullData title="Ooops, access denied!"/>
	}

	return (
		<div className="p-8">
			<Container>
				<div>
					<HomeBanner/>
				</div>
				{/* mapping all products */}
					<div className="grid
				 				grid-cols-2
								sm:grid-cols-3
								lg:grid-cols-4
								xl:grid-cols-5
								2xl:grid-cols-6
								gap-8">
					{products.map((product: any) => {
						// cutting the products name if longer 25 symb
						return <div key={product.id}><ProductCard product={product}/></div> 
					})}
				</div>
			</Container>
		</div>
	)
};
