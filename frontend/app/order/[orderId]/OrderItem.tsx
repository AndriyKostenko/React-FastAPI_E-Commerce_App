import { Item } from "@/app/admin/manage-orders/ManageClientOrder";

interface OrderItemProps {
	item: Item
}


const OrderItem:React.FC<OrderItemProps>= ({item}) => {
	return (
		<div className="grid grid-cols-5 tex-sx md:text-sm gap-4 border-t[1.5px] border-slate-200 py-4 items-center">
			<div>
				<div>
					
				</div>
			</div>
		</div>
	)
}

export default OrderItem;