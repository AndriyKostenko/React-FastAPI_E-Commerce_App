import CommunityGallery from "@/components/3. Community Gallery/CommunityGallery";
import FeaturedCollection from "@/components/4. Featured Collections/FeaturedCollection";
import Testimonials from "@/components/5. Testimonials/Testimonials";
import NullData from "@/components/ui/NullData";
import fetchProductsFromBackend from "../actions/getProducts";
import { Params, SearchParams } from "../types/params";
import HeroSection from "@/components/2. Hero/HeroComponentr";
import { sessionManagaer } from "@/actions/getCurrentUser";


export default async function Home(props: {params: Params, searchParams: SearchParams}) {
	const searchParams = await props.searchParams
    const searchTerm = searchParams['searchTerm'] as string | undefined;
    const category = searchParams['category'] as string | undefined;
    const products = await fetchProductsFromBackend(category, searchTerm);
	const currentUserJWT = await sessionManagaer.getCurrentUserJWT();

    if (!products || products.length === 0) {
        return <NullData title="No products!!!"/>
    }

    return (
        <div className="space-y-8">
			<HeroSection isRegisteredUser={Boolean(currentUserJWT)}
						 currentUserJWT={currentUserJWT} />
            <CommunityGallery />
            <FeaturedCollection products={products} />
            <Testimonials />
        </div>
    )
};
