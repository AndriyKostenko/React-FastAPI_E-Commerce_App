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
import { OrderProps } from '../../interfaces/order';


interface ManageOrdersClientProps{
  initialOrders: OrderProps[];
  token: string;
  expiryToken: number | null;
}


const ManagaeClientOrders:React.FC<ManageOrdersClientProps> = ({initialOrders, token, expiryToken}) => {

    const [orders, setOrders] = useState<OrderProps[]>(initialOrders);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState('');
	
	console.log('Token in manageClient>>>', token)
	console.log(orders)



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
	{field: 'user_id', headerName: 'User ID', width: 200},
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
	{field: 'payment_intent_id', headerName: 'Payment Intent', width: 200},

	{field: 'action', headerName: 'Actions', width: 200, renderCell: (params) => {
		return (<div className='flex justify-between gap-4 w-full'>
			<ActionBtn icon={MdDeliveryDining} onClick={() => {handleDispatch(params.row.id)}}/>
			<ActionBtn icon={MdDone} onClick={() => {handleDeliver(params.row.id)}}/>
			<ActionBtn icon={MdRemoveRedEye} onClick={() => {router.push(`/order/${params.row.id}`)}}/>
		</div>)
	}},
  ]


  const handleDispatch = useCallback((id: string) => {
    toast('Dispatching an order...');

	if (!token) {
      toast.error('No token found');
      return;
    }
    
    fetch(`http://127.0.0.1:8000/orders/${id}`, {
        method: 'PUT',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            delivery_status: 'dispatched'  // Pass delivery status in the body
        }),
    }).then(response => {
		if (response.ok) {
			toast.success('Order is updated');
			refreshOrders();
		}
	}).catch(error => {
		toast.error('Failed to update the oreder.');
		console.log('Error in handleToggleStock:', error)
	})}, [token]);


const handleDeliver = useCallback((id: string) => {
    toast('Updating delivery status to completed...');

	if (!token) {
      toast.error('No token found');
      return;
    }
    
    fetch(`http://127.0.0.1:8000/orders/${id}`, {
        method: 'PUT',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            status: 'completed'  // Pass delivery status in the body
        }),
    }).then(response => {
		if (response.ok) {
			toast.success('Order is updated');
			refreshOrders();
		}
	}).catch(error => {
		toast.error('Failed to update the oreder.');
		console.log('Error in handleToggleStock:', error)
	})}, [token]);




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


export default ManagaeClientOrders;