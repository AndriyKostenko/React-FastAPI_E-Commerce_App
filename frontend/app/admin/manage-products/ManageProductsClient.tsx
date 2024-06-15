'use client';

import { formatPrice } from '@/utils/formatPrice';
import { DataGrid, GridColDef} from '@mui/x-data-grid';
import { ProductProps } from '@/app/product/[productId]/ProductDetails';
import Heading from '@/app/components/Heading';
import Status from '@/app/components/Status';
import { MdDone } from 'react-icons/md';


interface ManageProductsClientProps{
  products: ProductProps[]
}

const ManageProductsClient:React.FC<ManageProductsClientProps> = ({products}) => {

  let rows: any = []

//   console.log('Products fot from backend: ', products)

  // creating rows for the table
  if (products) {

    rows = products.map((product) => {

      return {
        id: product.id,
        name: product.name,
		price: formatPrice(product.price),
		category: product.category.name,
		brand: product.brand,
		in_stock: product.in_stock,
		images: product.images 
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
	{field: 'category', headerName: 'Category', width: 100},
	{field: 'brand', headerName: 'Brand', width: 100},
	{field: 'in_stock', headerName: 'In Stock', width: 120, renderCell: (params) => {
		return (<div>{params.row.in_stock === true ? <Status text='in stock' icon={MdDone} background='bg-teal-200' color='text-teal-700'/> : 'out of stock'}</div>)
	}},
	{field: 'action', headerName: 'Actions', width: 200, renderCell: (params) => {
		return (<div>Action</div>)
	}},
  ]
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
			/>
		</div>
        
    </div>
  )
}

export default ManageProductsClient;