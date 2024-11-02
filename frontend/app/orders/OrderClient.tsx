'use client';

import { formatPrice } from '@/utils/formatPrice';
import { DataGrid, GridColDef} from '@mui/x-data-grid';
import Heading from '@/app/components/Heading';
import Status from '@/app/components/Status';
import { MdClose, MdDone, MdRemoveRedEye, MdDelete, MdDisabledVisible, MdAccessTimeFilled, MdDeliveryDining} from 'react-icons/md';
import ActionBtn from '@/app/components/ActionBtn';
import { useState, useCallback, useEffect } from 'react';
import toast from 'react-hot-toast';
import { useRouter } from 'next/navigation';
import fetchOrdersFromBackend from '@/actions/getOrders';
import { sessionManagaer } from "@/actions/getCurrentUser";
import { useCurrentUserTokenExpiryCheck } from "@/hooks/useCurrentUserToken";



interface ManageOrdersClientProps{
  userOrders: OrderProps[];
  token: string;
  expiryToken: number | null;
}

export interface OrderProps {
    id:                string;
    amount:            number;
    status:            string;
    create_date:       string;
    address_id:        string;
    user_id:           string;
    currency:          string;
    delivery_status:   string;
    payment_intent_id: string;
    items:             Item[];
}

export interface Item {
    id:         string;
    quantity:   number;
    order_id:   string;
    product_id: string;
    price:      number;
    product:    Product;
}

export interface Product {
    id:           string;
    name:         string;
    description:  string;
    brand:        string;
    price:        number;
    date_created: string;
    category_id:  string;
    quantity:     number;
    in_stock:     boolean;
    images:       Image[];
    category:     Category;
    reviews:      Review[];  // Assuming Review is an array
}

export interface Image {
    id:               string;
    image_color:      string;
    image_color_code: string;
    image_url:        string;
    product_id:       string;
}

export interface Category {
    id:   string;
    name: string;
}

export interface Review {
    // Define review properties as per your data model
}




const OrdersClient:React.FC<ManageOrdersClientProps> = ({userOrders, token, expiryToken}) => {

    const [orders, setOrders] = useState<OrderProps[]>(userOrders);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState('');
	

	// creating rows for the table
  	let rows: any = [];

	// Next.js router
	const router = useRouter();

    // redirecting back if token is expired
    useCurrentUserTokenExpiryCheck(expiryToken)



	// Function to refresh products from the backend
	const refreshOrders = async () => {
		setLoading(true);
		try {
			const refreshedOrders = await fetchOrdersFromBackend(token);
			setOrders([...refreshedOrders]);
		} catch (error) {
			toast.error("Failed to refresh orders");
			console.error("Error refreshing orders:", error);
		} finally {
			setLoading(false);
		}
	};


  // creating rows for the table
  if (orders) {

    rows = orders.map((order) => {

      return {
        id: order.id,
        amount: formatPrice(order.amount / 100),
		status: order.status,
		create_date: order.create_date,
		address_id: order.address_id,
		user_id: order.user_id,
		currency: order.currency,
		delivery_status: order.delivery_status,
		payment_intent_id: order.payment_intent_id

      }
    })
  }



  // creating columns for the table
  const columns: GridColDef[] = [
	// fields name should be equal to rows: id, name....
	{field: 'id', headerName: 'ID', width: 220},
	{field: 'amount', headerName: 'Amount (CAD)', width: 220},
	{field: 'status', headerName: 'Payment Status', width: 100, renderCell: (params: any) => {
		let background = '';
        let color = '';
        let icon = MdDone; // Default icon

		switch (params.row.status) {
                case 'pending':
                    background = 'bg-yellow-200';
                    color = 'text-yellow-700';
                    icon = MdAccessTimeFilled; // Example icon
                    break;
                case 'cancelled':
                    background = 'bg-red-200';
                    color = 'text-red-700';
                    icon = MdClose;
                    break;
                case 'complete':
                    background = 'bg-green-200';
                    color = 'text-green-700';
                    icon = MdDone;
                    break;
                default:
                    background = 'bg-gray-200';
                    color = 'text-gray-700';
                    icon = MdDone; // Default icon
            }
			return (
                <div>
                    <Status text={params.row.status} icon={icon} background={background} color={color} />
                </div>
            );
	}},
	{field: 'create_date', headerName: 'Date of creation', width: 200},
	{field: 'address_id', headerName: 'Address ID', width: 200},
	{field: 'currency', headerName: 'Currency', width: 200},
	{field: 'delivery_status', headerName: 'Delivery Status', width: 200, renderCell: (params: any) => {
		let background = '';
        let color = '';
        let icon = MdDone; // Default icon

		switch (params.row.delivery_status) {
                case 'pending':
                    background = 'bg-yellow-200';
                    color = 'text-yellow-700';
                    icon = MdAccessTimeFilled; // Example icon
                    break;
                case 'cancelled':
                    background = 'bg-red-200';
                    color = 'text-red-700';
                    icon = MdClose;
                    break;
                case 'dispatched':
                    background = 'bg-orange-200';
                    color = 'text-orange-700';
                    icon = MdDeliveryDining;
                    break;
                case 'delivered':
                    background = 'bg-green-200';
                    color = 'text-green-700';
                    icon = MdDone;
                    break;
                default:
                    background = 'bg-gray-200';
                    color = 'text-gray-700';
                    icon = MdDone; // Default icon
            }
			return (
                <div>
                    <Status text={params.row.delivery_status} icon={icon} background={background} color={color} />
                </div>
            ); 
		}
	},

	{field: 'action', headerName: 'Actions', width: 200, renderCell: (params) => {
		return (<div className='flex justify-between gap-4 w-full'>
			<ActionBtn icon={MdRemoveRedEye} onClick={() => {router.push(`/order/${params.row.id}`)}}/>
		</div>)
	}},
  ]

  return (
    <div className='max-w-[1150px] m-auto text-xl'>
		<div className='mb-4 mt-8'>
			<Heading title='Manage Orders' center/>
		</div>

		<div style={{height: 600, width: '100%'}}>
			<DataGrid
			rows={rows}
			columns={columns}
			initialState={{
				pagination: {
				paginationModel: { page: 0, pageSize: 5 },
				},
			}}
			pageSizeOptions={[5, 10]}
			checkboxSelection
			disableRowSelectionOnClick
			/>
		</div>
        
    </div>
  )
}


export default OrdersClient;