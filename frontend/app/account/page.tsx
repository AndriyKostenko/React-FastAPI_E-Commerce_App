import Container from "@/components/ui/Container";
import NullData from "@/components/ui/NullData";
import { sessionManagaer } from "@/actions/getCurrentUser";
import { fetchAccountProfile, fetchSavedAddresses } from "@/actions/getAccount";
import AccountClient from "./AccountClient";

/**
 * The signed-in user's account: profile, password, address book, deletion.
 * Read on the server with the user's token; the client sections change it
 * through the same-origin proxy.
 */
const AccountPage = async () => {
  const currentUserId = await sessionManagaer.getCurrentUserId();
  const token = await sessionManagaer.getCurrentUserJWT();
  if (!currentUserId || !token) {
    return <NullData title="Sign in to see your account." action={{ href: "/login", label: "Sign in" }} />;
  }

  const [profile, addresses] = await Promise.all([
    fetchAccountProfile(currentUserId, token),
    fetchSavedAddresses(token),
  ]);
  if (!profile) {
    return <NullData title="Your account could not be loaded. Please try again." />;
  }

  return (
    <div className="py-8">
      <Container>
        <AccountClient
          profile={profile}
          addresses={addresses}
          tokenExpiry={await sessionManagaer.getCurrentUserTokenExpiry()}
        />
      </Container>
    </div>
  );
};

export default AccountPage;
