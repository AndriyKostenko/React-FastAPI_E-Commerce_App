//import { products } from "@/utils/products";
import HomeBanner from "@/components/banner/HomeBanner";
import CommunityGallery from "@/components/sections/CommunityGallery";
import FeaturedCollection from "@/components/sections/FeaturedCollection";
import Testimonials from "@/components/sections/Testimonials";
import NullData from "@/components/NullData";
import fetchProductsFromBackend from "../actions/getProducts";

type Params = Promise<{ slug: string }>
type SearchParams = Promise<{ [key: string]: string | string[] | undefined }>

export async function generateMetadata(props: {
	params: Params
	searchParams: SearchParams
  }) {
	const params = await props.params
	const searchParams = await props.searchParams
	const slug = params.slug
	const query = searchParams.query
  }

export default async function Home(props: {
	params: Params
	searchParams: SearchParams
  }) {

	const searchParams = await props.searchParams
	const searchTerm = searchParams['searchTerm'] as string | undefined;
	const category = searchParams['category'] as string | undefined;

	console.log("searchParams", searchParams)

	// const products = await fetchProductsFromBackend(category, searchTerm);

	// if (!products || products.length === 0) {
	// 	return <NullData title="No products!!!"/>
	// }

	return (
		<div className="space-y-8">
			<HomeBanner />
			<CommunityGallery />
			{/*<FeaturedCollection products={products} />*/}
			<Testimonials />
		</div>
	)
};
