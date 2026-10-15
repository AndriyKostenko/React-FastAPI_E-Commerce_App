"use client";

import Heading from "@/components/ui/Heading";
import { useCurrentUserTokenExpiryCheck } from "@/hooks/useCurrentUserToken";
import type { AccountProfile, SavedAddress } from "@/types/account";
import AddressBook from "./AddressBook";
import DeleteAccountSection from "./DeleteAccountSection";
import PasswordSection from "./PasswordSection";
import ProfileSection from "./ProfileSection";

interface AccountClientProps {
  profile: AccountProfile;
  addresses: SavedAddress[];
  tokenExpiry: number | null;
}

const AccountClient: React.FC<AccountClientProps> = ({ profile, addresses, tokenExpiry }) => {
  useCurrentUserTokenExpiryCheck(tokenExpiry);

  return (
    <div className="max-w-4xl mx-auto flex flex-col gap-6">
      <Heading title="Your account" />
      <ProfileSection profile={profile} />
      <AddressBook initialAddresses={addresses} />
      <PasswordSection />
      <DeleteAccountSection userId={profile.id} />
    </div>
  );
};

export default AccountClient;
