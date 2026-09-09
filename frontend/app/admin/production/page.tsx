import fetchProductionQueue from "@/actions/getProductionQueue";
import { sessionManagaer } from "@/actions/getCurrentUser";
import NullData from "@/components/ui/NullData";
import ManageProductionClient from "@/app/admin/production/ManageProductionClient";

const OPEN_WORK = ["queued", "in_production", "printed", "on_hold"];

const ProductionQueue = async () => {
    const currentUserRole = await sessionManagaer.getCurrentUserRole();
    const currentUserToken = await sessionManagaer.getCurrentUserJWT();
    const expiryToken = await sessionManagaer.getCurrentUserTokenExpiry();

    if (currentUserRole !== "admin") {
        return <NullData title="Ooops, access denied!" />;
    }

    // Open work first: the queue exists to show what still has to be made.
    const queue = await fetchProductionQueue(currentUserToken, OPEN_WORK);

    return (
        <div>
            <ManageProductionClient
                initialQueue={queue}
                token={currentUserToken}
                expiryToken={expiryToken}
            />
        </div>
    );
};

export default ProductionQueue;
