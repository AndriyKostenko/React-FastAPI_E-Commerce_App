import CommunityGallery from "@/components/3. Community Gallery/CommunityGallery";
import FeaturedCollection from "@/components/4. Featured Collections/FeaturedCollection";
import Testimonials from "@/components/5. Testimonials/Testimonials";
import fetchProductCards from "@/actions/getProductCards";
import fetchFeaturedReviews from "@/actions/getFeaturedReviews";
import fetchBestSellers from "@/actions/getBestSellers";
import { BEST_SELLERS_SIZE } from "@/utils/collectionTabs";
import { Params, SearchParams } from "../types/params";
import HeroSection from "@/components/2. Hero/HeroComponentr";
import { sessionManagaer } from "@/actions/getCurrentUser";
import { toShopCard } from "@/utils/shopCard";


export default async function Home(props: {params: Params, searchParams: SearchParams}) {
	const searchParams = await props.searchParams
    const searchTerm = searchParams['searchTerm'] as string | undefined;
    const category = searchParams['category'] as string | undefined;
    const [products, reviews, bestSellers] = await Promise.all([
        fetchProductCards({ searchTerm, category }),
        fetchFeaturedReviews(),
        fetchBestSellers(BEST_SELLERS_SIZE),
    ]);
	const currentUserJWT = await sessionManagaer.getCurrentUserJWT();

    // if (!products || products.length === 0) {
    //     return <NullData title="No products!!!"/>
    // }

    return (
        <div className="space-y-8">
			<HeroSection isRegisteredUser={Boolean(currentUserJWT)} />
            <CommunityGallery />
            <FeaturedCollection products={products} bestSellers={bestSellers.map(({ product }) => toShopCard(product))} searchTerm={searchTerm?.trim() || undefined} />
            <Testimonials reviews={reviews} />
        </div>
    )
};
