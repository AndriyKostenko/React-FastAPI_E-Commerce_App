import Container from "@/components/ui/Container";
import NullData from "@/components/ui/NullData";
import { sessionManagaer } from "@/actions/getCurrentUser";
import { fetchWishlistEntries } from "@/actions/getWishlist";
import WishlistClient from "./WishlistClient";

/** The signed-in user's saved products, read on the server with their token. */
const WishlistPage = async () => {
  const token = await sessionManagaer.getCurrentUserJWT();
  if (!token) {
    return <NullData title="Sign in to see your wishlist." action={{ href: "/login", label: "Sign in" }} />;
  }
  const entries = await fetchWishlistEntries(token);
  if (entries === null) {
    return <NullData title="Your wishlist could not be loaded. Please try again." />;
  }
  return (
    <div className="py-8">
      <Container>
        <WishlistClient initialEntries={entries} />
      </Container>
    </div>
  );
};

export default WishlistPage;
