'use client';

import { formatPrice } from '@/utils/formatPrice';
import { DataGrid, GridColDef} from '@mui/x-data-grid';
import { ProductProps } from '@/app/product/[productId]/ProductDetails';
import Heading from '@/app/components/Heading';
import Status from '@/app/components/Status';
import { MdCached, MdClose, MdDone, MdRemoveRedEye, MdDelete, MdDisabledVisible} from 'react-icons/md';
import ActionBtn from '@/app/components/ActionBtn';
import { useState, useCallback, useEffect } from 'react';
import toast from 'react-hot-toast';
import { useRouter } from 'next/navigation';
import fetchOrdersFromBackend from '@/actions/getOrders';

const ManagaeClientOrders = ({initialOrders}) => {

    const [orders, setOrders] = useState<OrderProps[]>(initialOrders);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState('');

	// creating rows for the table
  	let rows: any = [];

	// Next.js router
	const router = useRouter();

	// Function to refresh products from the backend
	const refreshProducts = async () => {
		setLoading(true);
		try {
			const refreshedOrders = await fetchOrdersFromBackend();
			setOrders([...refreshedOrders]);
		} catch (error) {
			toast.error("Failed to refresh products");
			console.error("Error refreshing products:", error);
		} finally {
			setLoading(false);
		}
	};

	// Fetch fresh data when the component mounts
	// useEffect(() => {
	// 	refreshProducts();
	// }, []);
  
  


  // creating rows for the table
  if (orders) {

    rows = orders.map((order) => {

      return {
        id: product.id,
        name: product.name,
		price: formatPrice(product.price),
		category: product.category.name,
		brand: product.brand,
		in_stock: product.in_stock,
		images: product.images.map(image => image.image_url),
		quantity: product.quantity,
		description: product.description,
      }
    })
  }

  // creating columns for the table
  const columns: GridColDef[] = [
	// fields name should be equal to rows: id, name....
	{field: 'id', headerName: 'ID', width: 220},
	{field: 'name', headerName: 'Name', width: 220},
	{field: 'price', headerName: 'Price (CAD)', width: 100, renderCell: (params) => {
		return (<div className='font-bold text-slate-800'>{params.row.price}</div>)
	}},
	{field: 'images', headerName: 'Images', width: 200, renderCell: (params) => {
		return (<div className='flex gap-4'>
			{params.row.images.map((image: string, index: number) => {
				return (<img key={index} src={`http://localhost:8000${image}`} alt={params.row.name} className='w-16 h-16 object-cover'/>)
			})}
		</div>)}
	},
	{field: 'description', headerName: 'Description', width: 100},
	{field: 'quantity', headerName: 'Quantity', width: 100},
	{field: 'category', headerName: 'Category', width: 100},
	{field: 'brand', headerName: 'Brand', width: 100},
	{field: 'in_stock', headerName: 'In Stock', width: 120, renderCell: (params) => {
		return (<div>{params.row.in_stock === true ? (<Status text='in stock' icon={MdDone} background='bg-teal-200' color='text-teal-700'/>) : (<Status text='out of stock' icon={MdClose} background="bg-rose-200" color='text-rose-700'/>)}</div>)
	}},
	{field: 'action', headerName: 'Actions', width: 200, renderCell: (params) => {
		return (<div className='flex justify-between gap-4 w-full'>
			<ActionBtn icon={MdDisabledVisible} onClick={() => {handleToggleStock(params.row.id, params.row.in_stock)}}/>
			<ActionBtn icon={MdDelete} onClick={() => {handleDeleteProduct(params.row.id)}}/>
			<ActionBtn icon={MdRemoveRedEye} onClick={() => {router.push(`product/${params.row.id}`)}}/>
		</div>)
	}},
  ]

  // Function to toggle stock availability
  const handleToggleStock = useCallback((id: string, in_stock: boolean) => {
	fetch(`http://127.0.0.1:8000/update_product_availability/${id}?in_stock=${!in_stock}`, {
		method: 'PUT',
	}).then(response => {
		if (response.ok) {
			toast.success('Product stock updated successfully');
			refreshProducts();
		} 
	}).catch(error => {
		toast.error('Failed to update product stock')
		console.log('Error in handleToggleStock:', error)

  })}, [])

  // Function to delete a product
  const handleDeleteProduct = useCallback((id: string) => {
	toast('Deleting product...', {icon: '🗑️'});
	fetch(`http://127.0.0.1:8000/delete_product/${id}`, {
		method: 'DELETE',
	}).then(response => {
		if (response.ok) {
			toast.success('Product deleted successfully');
			refreshProducts();
		}
	}).catch(error => {
		toast.error('Failed to delete product');
		console.error('Error in handleDeleteProduct:', error);
	})
  	}, [])

  return (
    <div className='max-w-[1150px] m-auto text-xl'>
		<div className='mb-4 mt-8'>
			<Heading title='Manage Products' center/>
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