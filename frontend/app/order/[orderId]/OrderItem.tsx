"use client";

import { OrderItemProps as OrderLineItem } from "@/app/interfaces/order";
import { formatPrice } from "@/utils/formatPrice";
import { truncateText } from "@/utils/truncateText";
import Image from "next/image";
import { resolveImageUrl } from "@/utils/resolveImageUrl";

interface OrderItemProps {
	item: OrderLineItem;
}


const OrderItem:React.FC<OrderItemProps>= ({item}) => {
	console.log('Item in OrderItem:', item); // Log the item to see its structure

    const firstImage = resolveImageUrl(item.product?.images?.[0]?.image_url);
    const firstImageColor = item.product?.images?.[0]?.image_color || "n/a";
	console.log('First Image>>>>', firstImage)

	return (
		<div className="grid grid-cols-5 tex-sx md:text-sm gap-4 border-t[1.5px] border-slate-200 py-4 items-center">
			<div className="col-span-2 justify-self-start flex gap-2 md:gap-4">
				<div className="relative w-[70px] aspect-square">
					<Image src={firstImage}
					 		alt={item.product?.name || "Product Image"} 
							fill
							className="object-contain" 
					/>
				</div>
				<div className="flex flex-col gap-1">
					<div>{truncateText(item.product.name)}</div>
					<div>{firstImageColor}</div>
				</div>
			</div>

			<div className="justify-self-center" >{formatPrice(item.product.price)}</div>
			<div className="justify-self-center" >{item.product.quantity}</div>
			<div className="justify-self-end font-semibold" >$ {(item.product.price * item.product.quantity).toFixed(2)}</div>
		</div>
	)
}

export default OrderItem;
