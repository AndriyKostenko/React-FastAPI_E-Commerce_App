'use client';

import { ManageProductsClientProps } from "@/app/interfaces/admin";
import { ProductProps } from '@/app/interfaces/product';
import { formatPrice } from '@/utils/formatPrice';
import { DataGrid, GridColDef} from '@mui/x-data-grid';
import Heading from '@/app/components/Heading';
import Status from '@/app/components/Status';
import { MdClose, MdDone, MdRemoveRedEye, MdDelete, MdDisabledVisible} from 'react-icons/md';
import ActionBtn from '@/app/components/ActionBtn';
import { useState, useCallback } from 'react';
import toast from 'react-hot-toast';
import { useRouter } from 'next/navigation';
import fetchProductsFromBackend from '@/actions/getProducts';
import Image from 'next/legacy/image';
import { useCurrentUserTokenExpiryCheck } from "@/hooks/useCurrentUserToken";
import { resolveImageUrl } from '@/utils/resolveImageUrl';
import { settings } from "@/settings";

const ManageProductsClient:React.FC<ManageProductsClientProps> = ({initialProducts, expiryToken}) => {
const [products, setProducts] = useState<ProductProps[]>(initialProducts);
const [loading, setLoading] = useState(true);

  let rows: any = [];
  const router = useRouter();

  useCurrentUserTokenExpiryCheck(expiryToken)

const refreshProducts = async () => {
setLoading(true);
try {
const refreshedProducts = await fetchProductsFromBackend();
setProducts([...refreshedProducts]);
} catch (error) {
toast.error("Failed to refresh products");
console.error("Error refreshing products:", error);
} finally {
setLoading(false);
}
};

  if (products) {
    rows = products.map((product) => {
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

  const columns: GridColDef[] = [
{field: 'id', headerName: 'ID', width: 220},
{field: 'name', headerName: 'Name', width: 220},
{field: 'price', headerName: 'Price (CAD)', width: 100, renderCell: (params) => {
return (<div className='font-bold text-slate-800'>{params.row.price}</div>)
}},
{field: 'images', headerName: 'Images', width: 200, renderCell: (params) => {
return (<div className='flex gap-4'>
{params.row.images.map((image: string, index: number) => {
return (<Image width={100} height={100} key={index} src={resolveImageUrl(image)} alt={params.row.name} className='w-16 h-16 object-cover'/>)
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
<ActionBtn icon={MdRemoveRedEye} onClick={() => {router.push(`/products/${params.row.id}`)}}/>
</div>)
}},
  ]

  const handleToggleStock = useCallback((id: string, in_stock: boolean) => {
fetch(settings.api.backendEndpoints.updateProductAvailability(id, !in_stock), {
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

  const handleDeleteProduct = useCallback((id: string) => {
toast('Deleting product...', {icon: '🗑️'});
fetch(settings.api.backendEndpoints.deleteProduct(id), {
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

export default ManageProductsClient;
