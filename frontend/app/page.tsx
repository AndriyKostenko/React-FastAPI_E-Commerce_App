//import { products } from "@/utils/products";
import Container  from "./components/Container";
import HomeBanner from "./components/banner/HomeBanner";
import ProductCard from "./components/products/ProductCard";
import NullData from "./components/NullData";
import fetchProductsFromBackend from "../actions/getProducts";
import { ProductProps } from "./interfaces/product";




type Params = Promise<{ slug: string }>
type SearchParams = Promise<{ [key: string]: string | string[] | undefined }>

// this function will be called at build time for generating metadata
export async function generateMetadata(props: {
	params: Params
	searchParams: SearchParams
  }) {
	const params = await props.params
	const searchParams = await props.searchParams
	const slug = params.slug
	const query = searchParams.query
  }

// by default it's server component which will be rendered on t he server firsts
export default async function Home(props: {
	params: Params
	searchParams: SearchParams
  }) {

	const searchParams = await props.searchParams
	const searchTerm = searchParams['searchTerm'] as string | undefined;
	const category = searchParams['category'] as string | undefined;
	
	console.log("searchParams", searchParams)
  
	const products = await fetchProductsFromBackend(category, searchTerm);

	
	
	
	if (!products || products.length === 0) {
		return <NullData title="No products!!!"/>
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
					{products.map((product: ProductProps) => {
						// cutting the products name if longer 25 symb
						return <div key={product.id}><ProductCard product={product}/></div> 
					})}
				</div>
			</Container>
		</div>
	)
};
