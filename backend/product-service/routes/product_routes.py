from typing import List, Annotated, Optional

from fastapi import Depends, APIRouter, status, HTTPException, Form, UploadFile, File

from dependencies import get_product_service
from services.product_crud_service import ProductCRUDService
from models.product_models import Product
from schemas.product_schemas import ProductSchema, CreateProduct


product_routes = APIRouter(
    tags=["product"]
)


@product_routes.post("/products", 
                     status_code=status.HTTP_201_CREATED, 
                     response_model=Product,
                     response_description="New product created")
async def create_new_product(
                             name: str = Form(..., min_length=3, max_length=50),
                             description: str = Form(..., min_length=10, max_length=500),
                             category_id: str = Form(...),
                             brand: str = Form(...),
                             quantity: int = Form(..., ge=0, le=1000),
                             price: float = Form(..., ge=0, le=100),
                             in_stock: str = Form(...),
                             images_color: List[str] = Form(...),
                             images_color_code: List[str] = Form(...),
                             images: List[UploadFile] = File(...),
                             product_crud_service: ProductCRUDService = Depends(get_product_service),
                             ) -> Product:

    # convert in_stock to boolean coz it will be passed as a string from client
    if isinstance(in_stock, str):
        if in_stock.lower() == "true":
            in_stock = True
        else:
            in_stock = False
    
    image_paths = await product_crud_service.create_image_paths(images=images)

    # Validating that the lengths of the lists match....number of pict = color = color codes (only for inputs from
    # Swagger)
    # TODO : so, i have to get data from Form from client and its separating data correctly in the list...but
    #  when i do it from Swagger, all image_colors and image_color_codes are passed as a single string..so i have
    #  to split it

    # data from Swagger will be passed as a single string with comas, so i have to split it manually
    images_color = [color for colors in images_color for color in colors.split(',')]
    images_color_code = [code for codes in images_color_code for code in codes.split(',')]

    print(f"images_color: {images_color}, images_color_code: {images_color_code}, image_paths: {image_paths}")

    # if not matching - error
    if len(image_paths) != len(images_color) or len(image_paths) != len(images_color_code) or len(images_color) != len(images_color_code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Mismatch in the number of images and metadata")
        
    image_metadata = await product_crud_service.create_image_metadata(image_paths=image_paths, 
                                                 images_color=images_color,
                                                 images_color_code=images_color_code)

    new_product = await product_crud_service.create_product_item(CreateProduct(name=name,
                                                                               description=description,
                                                                               category_id=category_id,
                                                                               brand=brand,
                                                                               images=image_metadata,
                                                                               quantity=quantity,
                                                                               price=price,
                                                                               in_stock=in_stock))

    return new_product 



@product_routes.get("/products", 
                    status_code=status.HTTP_200_OK,
                    response_model=List[ProductSchema],
                    response_description="All products")
async def get_all_products(category: Optional[str] = None,
                           searchTerm: Optional[str] = None,
                           page: int = 1,
                           page_size: int = 10,
                           product_crud_service: ProductCRUDService = Depends(get_product_service)) -> List[ProductSchema]:
    try:
        products = await ProductCRUDService(session).get_all_products(category=category,
                                                                      searchTerm=searchTerm,
                                                                      page_size=page_size,
                                                                      page=page)
        if not products:
            raise HTTPException(status_code=404, detail="Products not found")
        return products # FastAPI automatically converts SQLAlchemy models into Pydantic models when response_model is used
            



@product_routes.get("/products/{product_id}", 
                    status_code=status.HTTP_200_OK,
                    response_model=ProductSchema,
                    response_description="Product by ID",
                    responses={
                        200: {"description": "Product by ID"},
                        404: {"description": "Product not found"},
                        500: {"description": "Internal server error"}})
async def get_product_by_id(product_id: str,
                            session: AsyncSession = Depends(get_db_session)) -> ProductSchema:
    try:
        product = await ProductCRUDService(session).get_product_by_id(product_id=product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product
    except DatabaseError as error:
        raise HTTPException(status_code=500, detail=str(error))
    

@product_routes.get("/products/name/{name}", 
                    status_code=status.HTTP_200_OK,
                    response_model=ProductSchema,
                    response_description="Product by name",
                    responses={
                        200: {"description": "Product by name"},
                        404: {"description": "Product not found"},
                        500: {"description": "Internal server error"}})
async def get_product_by_name(name: str,
                              session: AsyncSession = Depends(get_db_session)) -> ProductSchema:
    print(f"Name: {name}")
    try:
        product = await ProductCRUDService(session).get_product_by_name(name=name)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product
    except DatabaseError as error:
        raise HTTPException(status_code=500, detail=str(error))
 

@product_routes.put("/products/{product_id}", 
                    status_code=status.HTTP_200_OK,
                    response_model=ProductSchema,
                    response_description="Product availability updated",
                    responses={
                        200: {"description": "Product availability updated"},
                        404: {"description": "Product not found"},
                        500: {"description": "Internal server error"}})
async def update_product_availability(product_id: str,
                                      in_stock: bool,
                                      session: AsyncSession = Depends(get_db_session)) -> ProductSchema:
    try:
        product = await ProductCRUDService(session=session).update_product_availability(product_id=product_id, in_stock=in_stock)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product
    except DatabaseError as error:
        raise HTTPException(status_code=500, detail=str(error))
        
    
@product_routes.delete("/products/{product_id}", 
                       status_code=status.HTTP_204_NO_CONTENT,
                       response_description="Product deleted",
                       responses={
                           204: {"description": "Product deleted"},
                           401: {"description": "Unauthorized"},
                           404: {"description": "Product not found"},
                           500: {"description": "Internal server error"}})
async def delete_product(product_id: str,
                         current_user: Annotated[dict, Depends(auth_manager.get_current_user_from_token)],
                         session: AsyncSession = Depends(get_db_session)) -> None:
    if current_user["user_role"] != "admin" or current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    try:
        deleted_product = await ProductCRUDService(session).delete_product(product_id=product_id)
        if not deleted_product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    except DatabaseError as error:
        raise HTTPException(status_code=500, detail=str(error))

