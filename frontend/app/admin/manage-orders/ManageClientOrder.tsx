'use client';

import { AdminManageOrdersClientProps } from '@/app/interfaces/admin';
import { OrderProps } from '@/app/interfaces/order';
import { formatPrice } from '@/utils/formatPrice';
import { DataGrid, GridColDef} from '@mui/x-data-grid';
import Heading from '@/app/components/Heading';
import Status from '@/app/components/Status';
import { MdClose, MdDone, MdRemoveRedEye, MdAccessTimeFilled, MdDeliveryDining} from 'react-icons/md';
import ActionBtn from '@/app/components/ActionBtn';
import { useState, useCallback } from 'react';
import toast from 'react-hot-toast';
import { useRouter } from 'next/navigation';
import fetchOrdersFromBackend from '@/actions/getOrders';
import { useCurrentUserTokenExpiryCheck } from "@/hooks/useCurrentUserToken";
import { settings } from "@/settings";

const ManagaeClientOrders:React.FC<AdminManageOrdersClientProps> = ({initialOrders, token, expiryToken}) => {
    const [orders, setOrders] = useState<OrderProps[]>(initialOrders);
const [loading, setLoading] = useState(true);

  let rows: any = [];
  const router = useRouter();

  useCurrentUserTokenExpiryCheck(expiryToken)

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

  if (orders) {
    rows = orders.map((order) => {
      return {
        id: order.id,
        amount: formatPrice(order.amount / 100),
status: order.status,
date_created: order.date_created,
address_id: order.address_id,
user_id: order.user_id,
currency: order.currency,
delivery_status: order.delivery_status,
payment_intent_id: order.payment_intent_id
      }
    })
  }

  const columns: GridColDef[] = [
{field: 'id', headerName: 'ID', width: 220},
{field: 'amount', headerName: 'Amount (CAD)', width: 220},
{field: 'status', headerName: 'Payment Status', width: 100, renderCell: (params: any) => {
let background = '';
        let color = '';
        let icon = MdDone;

switch (params.row.status) {
                case 'pending':
                    background = 'bg-yellow-200';
                    color = 'text-yellow-700';
                    icon = MdAccessTimeFilled;
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
                    icon = MdDone;
            }
return (
                <div>
                    <Status text={params.row.status} icon={icon} background={background} color={color} />
                </div>
            );
}},
{field: 'date_created', headerName: 'Date of creation', width: 200},
{field: 'address_id', headerName: 'Address ID', width: 200},
{field: 'user_id', headerName: 'User ID', width: 200},
{field: 'currency', headerName: 'Currency', width: 200},
{field: 'delivery_status', headerName: 'Delivery Status', width: 200, renderCell: (params: any) => {
let background = '';
        let color = '';
        let icon = MdDone;

switch (params.row.delivery_status) {
                case 'pending':
                    background = 'bg-yellow-200';
                    color = 'text-yellow-700';
                    icon = MdAccessTimeFilled;
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
                    icon = MdDone;
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

    fetch(settings.api.backendEndpoints.updateOrder(id), {
        method: 'PUT',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            delivery_status: 'dispatched'
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

    fetch(settings.api.backendEndpoints.updateOrder(id), {
        method: 'PUT',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            status: 'completed'
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
