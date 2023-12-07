import { products } from "@/utils/products";
import  Container  from "./components/Container";
import HomeBanner from "./components/banner/HomeBanner";
import { truncateText } from "@/utils/truncateText";
import ProductCard from "./components/products/ProductCard";


// server component which will be rendered on t he server firsts
export default function Home() {
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
						return <div key={product.id}><ProductCard data={product}/></div> 
					})}
				</div>
			</Container>
		</div>
	)
};
