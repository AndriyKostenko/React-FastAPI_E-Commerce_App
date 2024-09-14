from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict
from src.models.product_models import Product, ProductImage, ProductCategory, ProductReview
from sqlalchemy import select, asc, desc
from src.schemas.product_schemas import CreateProduct, ProductSchema, CreateProductReview
from src.schemas.product_schemas import ImageType


class ProductCRUDService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_product_item(self, product: CreateProduct):

        # getting product category.id for creation of new product, if no -> first creating category to connect with
        # Product
        product_category = await self.get_product_category_by_name(category=product.category)
        if not product_category:
            product_category = await self.create_product_category(category=product.category)

        # creating new product
        new_product = Product(name=product.name,
                              description=product.description,
                              category_id=product_category.id,
                              brand=product.brand,
                              quantity=product.quantity,
                              price=product.price,
                              in_stock=product.in_stock, )
        self.session.add(new_product)
        await self.session.commit()

        # creating product images
        new_product_images = await self.create_product_image(product_id=new_product.id, image_data=product.images)
        self.session.add(new_product_images)

        await self.session.commit()
        await self.session.refresh(new_product)
        return new_product

    async def get_all_products(self, category: Optional[str] = None, searchTerm: Optional[str] = None):
        # it works in way that it first loads all products, then loads images, reviews and category for each product
        # according to relations in models
        query = select(Product).options(
            selectinload(Product.images),
            selectinload(Product.reviews).selectinload(ProductReview.user),  # product review is connected with user
            selectinload(Product.category)
        ).order_by(desc(Product.date_created))

        if category:
            query = query.filter(Product.category.has(name=category))

        if searchTerm:
            query = query.filter(Product.name.ilike(f"%{searchTerm}%"))

        result = await self.session.execute(query)
        products = result.scalars().all()

        #TODO: cant return a specific product format, its returning the list of Procut classes...returning products according to models right now

        return products
        # return [product.to_dict() for product in products]
        # return [{"id": p.id,
        #          "name": p.name,
        #          'description': p.description,
        #          'price': p.price,
        #          'category':p.category,
        #          'in_stock': p.in_stock} for p in products]

    async def get_product_by_id(self, product_id: str):
        db_product = await self.session.execute(select(Product).where(Product.id == product_id))
        return db_product.scalars().first()

    async def create_product_category(self, category: str):

        db_category = await self.session.execute(select(ProductCategory).where(ProductCategory.name == category))
        db_category = db_category.scalars().first()
        if db_category:
            return db_category

        new_category = ProductCategory(name=category)
        self.session.add(new_category)
        await self.session.commit()
        return new_category

    async def get_product_category_by_name(self, category: str):
        db_category = await self.session.execute(select(ProductCategory).where(ProductCategory.name == category))
        if db_category:
            return db_category.scalars().first()
        return None

    async def create_product_image(self, product_id: str, image_data: List[ImageType]):
        # Iterate over the images and save each one
        for data in image_data:
            new_product_image = ProductImage(product_id=product_id,
                                             image_url=data.image,
                                             image_color=data.color,
                                             image_color_code=data.color_code)
            self.session.add(new_product_image)

        await self.session.commit()
        # TODO: rewrite functionality to return single new_product_image
        return new_product_image


    async def create_product_review(self, product_review: CreateProductReview):
        new_review = ProductReview(product_id=product_review.product_id,
                                   comment=product_review.comment,
                                   user_id=product_review.user_id,
                                   rating=product_review.rating)
        self.session.add(new_review)
        await self.session.commit()
        return new_review

    async def update_product_availability(self, product_id: str, in_stock: bool):
        db_product = await self.session.execute(select(Product).where(Product.id == product_id))
        db_product = db_product.scalars().first()

        if db_product:
            db_product.in_stock = in_stock
            await self.session.commit()
            return db_product
        return None

    async def delete_product(self, product_id: str):
        db_product = await self.session.execute(select(Product).where(Product.id == product_id))
        db_product = db_product.scalars().first()

        if db_product:
            await self.session.delete(db_product)
            await self.session.commit()
            return True
        else:
            return False