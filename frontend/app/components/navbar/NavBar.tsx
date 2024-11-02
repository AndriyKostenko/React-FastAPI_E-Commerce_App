import Container from "../Container";
import Link from "next/link";
import { Redressed } from "next/font/google";
import CartCount from "./CartCount";
import UserMenu from "./UserMenu";
import { sessionManagaer} from "@/actions/getCurrentUser";
import Categories from "./Categories";
import fetchCategoriesFromBackend from "@/actions/getCategories";

// setting the font
const redressed = Redressed({subsets: ['latin'],
                            weight: ['400'] })


const NavBar = async () => {
    // getting current user from the session
    const currentUser = await sessionManagaer.getCurrentUser();
    const currentUserRole = await sessionManagaer.getCurrentUserRole();
    const categories = await fetchCategoriesFromBackend()

    return (
        <div className="sticky
                        top-0
                        w-full
                        bg-slate-200
                        z-30
                        shadow-sm">
            <div className="py-4 
                            border-b-[1px]">
                <Container>
                    <div className="flex
                                    items-center
                                    justify-between
                                    gap-3
                                    md:gap-0">
                        {/* changing the font and adding more classes */}
                        <Link href='/' className={`${redressed.className} font-bold text-2xl`}>
                            E-Commerce App
                        </Link>

                        {/* making hiden for smaller screens */}
                        <div className="hidden 
                                        md:block">Search</div>

                        <div className="flex 
                                        items-center
                                        gap-8
                                        md:gap-12">
                            <CartCount/>
                            
                            <UserMenu currentUser={currentUser} currentUserRole={currentUserRole}/>
                        </div>

                    </div>

                </Container>
            </div>
            <Categories categories={categories}/>
        </div>
    );
}


export default NavBar;

