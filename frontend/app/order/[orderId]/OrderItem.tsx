"use client";

import { Item, OrderProps } from "@/app/admin/manage-orders/ManageClientOrder";
import { formatPrice } from "@/utils/formatPrice";
import { truncateText } from "@/utils/truncateText";
import src from "@emotion/styled";
import { log } from "console";
import Image from "next/image";

interface OrderItemProps {
	item: Item;
}


const OrderItem:React.FC<OrderItemProps>= ({item}) => {
	console.log('Item in OrderItem:', item); // Log the item to see its structure

    const firstImage = item.product?.images?.[0]?.image_url || "/path/to/default_image.jpg"; // Fallback image URL
	console.log('First Image>>>>', firstImage)

	return (
		<div className="grid grid-cols-5 tex-sx md:text-sm gap-4 border-t[1.5px] border-slate-200 py-4 items-center">
			<div className="col-span-2 justify-self-start flex gap-2 md:gap-4">
				<div className="relative w-[70px] aspect-square">
					<Image src={`http://localhost:8000${firstImage}`} 
					 		alt={item.product?.name || "Product Image"} 
							fill
							className="object-contain" 
					/>
				</div>
				<div className="flex flex-col gap-1">
					<div>{truncateText(item.product.name)}</div>
					<div>{item.product.images[0].image_color}</div>
				</div>
			</div>

			<div className="justify-self-center" >{formatPrice(item.product.price)}</div>
			<div className="justify-self-center" >{item.product.quantity}</div>
			<div className="justify-self-end font-semibold" >$ {(item.product.price * item.product.quantity).toFixed(2)}</div>
		</div>
	)
}

export default OrderItem;