'use client'

import { Avatar } from "@mui/material";
import { useCallback, useState } from "react";
import { AiFillCaretDown } from "react-icons/ai";
import MenuItem from "./MenuItem";
import Link from "next/link";
import BackDrop from "./BackDrop";
import { signOut } from "next-auth/react";


interface UserMenuProps {
    currentUser?: {
        name?: string | null | undefined,
        email?: string | null | undefined,
        image?: string | null | undefined
    } | null;
    currentUserRole?: string | null | undefined;
}



const UserMenu:React.FC<UserMenuProps> = ({currentUser, currentUserRole}) => {

    const [isOpen, setIsOpen] = useState(false);

    const toggleOpen = useCallback(() => {
        setIsOpen((prev) => !prev)
    }, [])

    return (
        <>
            <div className="relative z-30">
                <div onClick={toggleOpen} className="p-2 
                                                    border-[1px] 
                                                    border-slate-400
                                                    flex
                                                    flex-row
                                                    items-center
                                                    gap-1
                                                    rounded-full
                                                    cursor-pointer
                                                    hover:shadow-md
                                                    transition
                                                    text-slate-700">

                    <Avatar src={currentUser?.image || undefined}/>
                    <AiFillCaretDown/>
                </div>
            {isOpen && (
                <div className="absolute 
                                rounded-md
                                shadow-md
                                w-[170px]
                                bg-white
                                overflow-hidden
                                right-0
                                top-12
                                text-sm
                                flex
                                flex-col
                                cursor-pointer
                                "
                    >
                    {currentUser !== undefined && currentUser!== null ? 
                        <div>
                            <Link href="/orders">
                                <MenuItem onClick={toggleOpen}>Your Orders</MenuItem>
                            </Link>

                            <MenuItem onClick={() => {
                                toggleOpen();
                                signOut()
                            }}>Logout</MenuItem>
                        </div> :
                        <div>
                            <Link href="/login">
                                <MenuItem onClick={toggleOpen}>Login</MenuItem>
                            </Link>

                            <Link href="/register">
                                <MenuItem onClick={toggleOpen}>Register</MenuItem>
                        </Link>
                        </div>
                    }
                    {currentUserRole == 'admin' &&  
                            <Link href="/admin">
                                <MenuItem onClick={toggleOpen}>Admin Dashboard</MenuItem>
                            </Link>
                    }



                </div>
                )}    
            </div>
            {isOpen ? <BackDrop onClick={toggleOpen}/> : null}
        </>
);
}
 
export default UserMenu;