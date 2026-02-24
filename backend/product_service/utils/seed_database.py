"""
Seed Utility — load fake categories, products, and product images into the
Product-Service database.

Usage (run from the product_service/ directory):

    # Basic seed — 5 products per category
    python utils/seed_fake_products.py

    # Customise product count per category
    python utils/seed_fake_products.py --products-per-category 10

    # Also seed placeholder product images (2-3 per product)
    python utils/seed_fake_products.py --with-images

    # Wipe all existing seed data first, then re-seed
    python utils/seed_fake_products.py --clear

    # Combine flags
    python utils/seed_fake_products.py --products-per-category 8 --with-images --clear
"""

import sys
import os
import asyncio
import argparse
import random
from decimal import Decimal
from uuid import UUID

# ---------------------------------------------------------------------------
# Ensure product_service/ is on sys.path so local imports (models.*, etc.) work
# regardless of where the script is executed from.
# ---------------------------------------------------------------------------
_SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SERVICE_DIR not in sys.path:
    sys.path.insert(0, _SERVICE_DIR)

from shared.database_setup import DatabaseSessionManager  # type: ignore
from shared.logger_config import setup_logger             # type: ignore
from shared.settings import get_settings                  # type: ignore

from models.category_models import ProductCategory        # type: ignore
from models.product_models import Product                 # type: ignore
from models.product_image_models import ProductImage      # type: ignore
from models.review_models import ProductReview            # type: ignore  # noqa: F401 — not used directly, but must be imported so SQLAlchemy can resolve the 'ProductReview' forward-reference in Product.reviews

from database_layer.category_repository import CategoryRepository      # type: ignore
from database_layer.product_repository import ProductRepository        # type: ignore
from database_layer.product_image_repository import ProductImageRepository  # type: ignore



# ---------------------------------------------------------------------------
# Static fake-data tables
# ---------------------------------------------------------------------------

FAKE_CATEGORIES: list[dict] = [
    {"name": "Electronics",   "image_url": "https://placehold.co/400x300/0ea5e9/white?text=Electronics"},
    {"name": "Clothing",      "image_url": "https://placehold.co/400x300/8b5cf6/white?text=Clothing"},
    {"name": "Home & Garden", "image_url": "https://placehold.co/400x300/22c55e/white?text=Home+%26+Garden"},
    {"name": "Sports",        "image_url": "https://placehold.co/400x300/f97316/white?text=Sports"},
    {"name": "Books",         "image_url": "https://placehold.co/400x300/eab308/white?text=Books"},
    {"name": "Beauty",        "image_url": "https://placehold.co/400x300/ec4899/white?text=Beauty"},
    {"name": "Toys",          "image_url": "https://placehold.co/400x300/ef4444/white?text=Toys"},
    {"name": "Furniture",     "image_url": "https://placehold.co/400x300/6366f1/white?text=Furniture"},
]

# Products keyed by category name.  Each entry is a (name, brand, description) tuple.
FAKE_PRODUCTS_BY_CATEGORY: dict[str, list[tuple[str, str, str]]] = {
    "Electronics": [
        ("wireless noise-cancelling headphones", "SoundCore",  "Premium over-ear headphones with 30-hour battery life and active noise cancellation."),
        ("4k ultra hd smart tv 55-inch",         "VisionTech", "Crisp 4K display with built-in streaming apps, Dolby Vision, and voice control."),
        ("mechanical gaming keyboard",           "KeyForge",   "Tactile blue switches, RGB backlight, and full N-key rollover for competitive gaming."),
        ("portable bluetooth speaker",           "BoomBox",    "360-degree surround sound with IPX7 water resistance and 20-hour playtime."),
        ("true wireless earbuds",                "AirBud",     "Compact earbuds with touch controls, 6-hour battery, and wireless charging case."),
        ("gaming mouse 16000 dpi",               "SwiftClick", "Ergonomic design with 11 programmable buttons and adjustable DPI up to 16,000."),
        ("usb-c 100w charging hub",              "PowerLink",  "7-in-1 hub with HDMI 4K, 3x USB-A, SD card reader, and 100 W pass-through charging."),
        ("smart home security camera",           "GuardEye",   "1080p HD indoor/outdoor camera with night vision and two-way audio."),
        ("wireless charging pad 15w",            "ChargeFast", "Qi-certified fast-charging pad compatible with all Qi-enabled smartphones."),
        ("portable solar power bank 26800mah",   "SolarBoost", "Solar + USB dual charging, 26800 mAh capacity, charges three devices simultaneously."),
    ],
    "Clothing": [
        ("men's slim-fit chino trousers",        "UrbanThread",   "Stretch cotton chinos with a tailored slim fit, available in 12 colours."),
        ("women's oversized knit sweater",       "CozyWear",      "100% merino wool oversized pullover with ribbed cuffs and hem."),
        ("unisex zip-up hoodie",                 "StreetVibe",    "French-terry cotton blend hoodie with kangaroo pocket and YKK zipper."),
        ("women's high-waist yoga leggings",     "FlexFit",       "4-way stretch fabric with moisture-wicking finish and hidden waistband pocket."),
        ("men's waterproof hiking jacket",       "TrailEdge",     "Seam-sealed shell with 3-layer Gore-Tex and underarm vents."),
        ("women's linen midi dress",             "SunDrift",      "Breathable linen blend dress with adjustable tie waist, perfect for summer."),
        ("men's merino wool crew-neck tee",      "BaseLayer",     "Ultra-soft 18.5 micron merino tee, naturally odour-resistant and temperature-regulating."),
        ("kids' puffer jacket",                  "LittleExplorer","Lightweight recycled-fill puffer with reflective strips and detachable hood."),
        ("women's leather ankle boots",          "SoleMate",      "Genuine full-grain leather boots with cushioned insole and block heel."),
        ("men's athletic running shorts",        "SprintGear",    "Lightweight 2-in-1 shorts with 7-inch inseam, zip pocket, and built-in liner."),
    ],
    "Home & Garden": [
        ("stainless steel cookware set 10-piece","ChefSelect",  "Tri-ply stainless steel pots and pans with stay-cool handles and glass lids."),
        ("robotic vacuum cleaner",               "CleanBot",    "Auto-mapping robot vacuum with HEPA filter, Wi-Fi control, and 120-min runtime."),
        ("memory foam mattress queen",           "DreamRest",   "CertiPUR-US certified 12-inch memory foam mattress with cooling gel layer."),
        ("outdoor solar garden lights set of 6","SunPath",     "Waterproof LED path lights that automatically turn on at dusk."),
        ("kitchen stand mixer 5.5qt",            "BakeMaster",  "Tilt-head mixer with 10 speeds, stainless steel bowl, and dough hook attachment."),
        ("air purifier hepa 1500 sq ft",         "PureAir",     "True HEPA + activated carbon filter capturing 99.97% of particles 0.3 microns and larger."),
        ("cotton percale sheet set queen",       "LinenLoft",   "200-thread-count 100% long-staple cotton sheets, crisp and breathable."),
        ("plant grow light full spectrum",       "GrowLux",     "Full-spectrum LED grow light with timer, dimmer, and flexible gooseneck arm."),
        ("cast iron dutch oven 6qt",             "IronKitchen", "Pre-seasoned cast iron with enamelled interior, oven-safe to 500 F."),
        ("cordless electric lawn mower",         "GreenCut",    "40V lithium battery mower with 16-inch cutting deck and 3-in-1 grass management."),
    ],
    "Sports": [
        ("adjustable dumbbell set 5-52.5 lbs",  "IronCore",   "Replaces 15 sets of weights with a single dial adjustment system."),
        ("yoga mat non-slip 6mm",                "ZenFlow",    "Extra-thick 6 mm TPE mat with alignment lines and carrying strap."),
        ("carbon fibre road bike",               "VeloRace",   "11-speed Shimano 105 groupset, carbon fork, and aero tube geometry."),
        ("foam roller deep tissue",              "RecoverPro", "High-density EPP foam roller for myofascial release and muscle recovery."),
        ("jump rope speed cable",                "JumpFast",   "Lightweight aluminium handles with adjustable 10-foot steel cable."),
        ("resistance bands set 5-levels",        "BandForce",  "Natural latex bands with fabric handles, door anchor, and carry bag."),
        ("pull-up bar doorframe",                "GripMaster", "Multi-grip steel bar, no screws needed, supports up to 300 lbs."),
        ("cycling helmet mips",                  "SafeRide",   "MIPS-equipped road helmet with 20 vents and adjustable fit dial."),
        ("running shoes lightweight",            "StridePro",  "Engineered mesh upper with responsive EVA foam midsole for long-distance comfort."),
        ("smart fitness tracker band",           "FitPulse",   "24/7 heart rate, SpO2, sleep tracking, and 7-day battery life."),
    ],
    "Books": [
        ("clean code by robert c. martin",        "Prentice Hall",  "A handbook of agile software craftsmanship for writing readable, maintainable code."),
        ("designing data-intensive applications", "O'Reilly",       "Deep dive into the principles behind reliable, scalable, and maintainable systems."),
        ("the pragmatic programmer",              "Addison-Wesley", "Classic career-defining guide to becoming a better software developer."),
        ("atomic habits by james clear",          "Avery",          "Practical framework for building good habits and breaking bad ones."),
        ("sapiens by yuval noah harari",          "Harper",         "A brief history of humankind spanning 70,000 years of human civilisation."),
        ("zero to one by peter thiel",            "Crown Business", "Notes on startups and how to build companies that create new things."),
        ("the lean startup",                      "Crown Business", "How today's entrepreneurs use continuous innovation to create successful businesses."),
        ("deep work by cal newport",              "Grand Central",  "Rules for focused success in a distracted world."),
        ("thinking fast and slow",                "Farrar Straus",  "Daniel Kahneman explores the two systems that drive the way we think."),
        ("the hitchhiker's guide to the galaxy",  "Pan Books",      "The comedic space odyssey following Arthur Dent across the universe."),
    ],
    "Beauty": [
        ("vitamin c brightening serum",          "GlowLab",     "20% L-ascorbic acid serum with hyaluronic acid and ferulic acid stabiliser."),
        ("retinol anti-ageing night cream",      "AgelessSkin", "0.3% encapsulated retinol with ceramides for overnight skin renewal."),
        ("spf 50 tinted moisturiser",            "SheerShield", "Lightweight daily moisturiser with mineral SPF 50 and light-diffusing pigments."),
        ("hyaluronic acid hydrating toner",      "AquaDew",     "Multi-molecular weight HA toner for plump, dewy skin in seconds."),
        ("jade face roller and gua sha set",     "CrystalRite", "Genuine jade roller and gua sha stone for lymphatic drainage and de-puffing."),
        ("niacinamide 10% + zinc pore serum",    "ClearSkin",   "Reduces appearance of blemishes, pores, and excess oil production."),
        ("electric facial cleansing brush",      "SonicGlow",   "Sonic oscillation brush with silicone head, 3 speeds, and waterproof body."),
        ("lip plumping gloss set of 4",          "PlumpKiss",   "Peptide-infused glosses that volumise lips while delivering intense moisture."),
        ("professional hair dryer 2200w",        "SilkDry",     "Ionic ceramic dryer with concentrator and diffuser attachments, 2200 W motor."),
        ("collagen eye patches 60 pairs",        "EyeRevive",   "Hydrogel patches infused with collagen, gold, and green tea extract."),
    ],
    "Toys": [
        ("lego city police station 743 pieces",  "LEGO",          "Build and play with a detailed police station, helicopter, and 5 minifigures."),
        ("remote control off-road truck",        "TurboRacer",    "1:10 scale 4WD rock crawler with 2.4 GHz remote, independent suspension."),
        ("wooden stacking blocks 50 piece",      "TinkerTots",    "Smooth, non-toxic hardwood blocks in 4 shapes to encourage open-ended play."),
        ("interactive robot dog",                "RoboPaws",      "AI-powered pup that responds to voice, touch, and learns new tricks."),
        ("magnetic drawing board xl",            "DrawMagic",     "Extra-large erasable board with colour sections and slide eraser."),
        ("kids coding robot starter kit",        "CodeBuddy",     "Block-based programming robot for ages 5+ that makes learning to code fun."),
        ("slime making science kit",             "GooLab",        "12 experiments, all materials included, introduces basic chemistry concepts."),
        ("professional art set 138 pieces",      "ArtMaster",     "Coloured pencils, pastels, watercolours, and brushes in a carry case."),
        ("balance bike for toddlers",            "PedalStart",    "Lightweight aluminium balance bike, adjustable seat, for ages 18 months to 5 years."),
        ("miniature dollhouse with furniture",   "DreamHome",     "Handcrafted 1:12 scale dollhouse with LED lights and 40+ furniture pieces."),
    ],
    "Furniture": [
        ("ergonomic office chair lumbar support","ComfortSeat",  "Mesh back, 4D armrests, adjustable lumbar, and tilt-tension control."),
        ("solid oak dining table 6-seater",      "TimberCraft",  "Hand-finished solid oak table with breadboard ends and tapered legs."),
        ("modular l-shaped sofa",                "LivingSpace",  "Reversible chaise, high-resilience foam, removable washable covers."),
        ("king size platform bed frame",         "SlumberCo",    "Solid pine slat base with USB headboard charging ports and under-bed storage."),
        ("floating wall shelves set of 3",       "ShelfUp",      "Powder-coated steel brackets with solid walnut shelves, 60 kg capacity each."),
        ("standing desk electric height adj.",   "DeskRise",     "Dual-motor sit-stand desk, 3 memory presets, cable management tray."),
        ("bookcase with glass doors 5-shelf",    "LibraryOak",   "Solid oak bookcase with adjustable shelves behind tempered glass doors."),
        ("extendable coffee table",              "LoftLiving",   "Walnut veneer top that extends from 90 to 180 cm, hidden storage drawer."),
        ("rattan outdoor dining set 6-piece",    "GardenElite",  "All-weather PE rattan set with tempered glass table and cushioned chairs."),
        ("wardrobe with sliding mirror doors",   "ClosetPro",    "2.2 m wardrobe with full-length mirror doors and internal drawer unit."),
    ],
}

# Colour palettes used when generating product images
_COLOUR_MAP: list[tuple[str, str]] = [
    ("Black",       "#000000"),
    ("White",       "#FFFFFF"),
    ("Navy Blue",   "#1e3a5f"),
    ("Forest Green","#228B22"),
    ("Burgundy",    "#800020"),
    ("Charcoal",    "#36454F"),
    ("Slate Gray",  "#708090"),
    ("Sand",        "#C2B280"),
    ("Rose Gold",   "#B76E79"),
    ("Sky Blue",    "#87CEEB"),
]


# ---------------------------------------------------------------------------
# Helper: build a standalone DatabaseSessionManager
# ---------------------------------------------------------------------------

def _make_db_manager(settings, logger) -> DatabaseSessionManager:
    """Build a lean DatabaseSessionManager for the product-service DB."""
    return DatabaseSessionManager(
        database_url=settings.PRODUCT_SERVICE_DATABASE_URL,
        engine_settings={
            "echo": False,
            "pool_pre_ping": True,
            "pool_size": 5,
            "max_overflow": 0,
        },
        logger=logger,
    )


# ---------------------------------------------------------------------------
# Step 1: clear (optional)
# ---------------------------------------------------------------------------

async def _clear_existing_data(
    category_repo: CategoryRepository,
    product_repo: ProductRepository,
    logger,
) -> None:
    """Delete all products first (FK), then all categories."""
    all_products = await product_repo.get_all(limit=None)
    if all_products:
        await product_repo.delete_many(all_products)
        logger.info(f"  Deleted {len(all_products)} existing product(s).")

    all_categories = await category_repo.get_all(limit=None)
    if all_categories:
        await category_repo.delete_many(all_categories)
        logger.info(f"  Deleted {len(all_categories)} existing categor(ies).")


# ---------------------------------------------------------------------------
# Step 2: categories
# ---------------------------------------------------------------------------

async def _seed_categories(
    category_repo: CategoryRepository,
    logger,
) -> dict[str, UUID]:
    """
    Insert categories that don't already exist.
    Returns a mapping of  category_name -> category.id.
    """
    name_to_id: dict[str, UUID] = {}

    for cat in FAKE_CATEGORIES:
        existing = await category_repo.get_by_field("name", cat["name"])
        if existing:
            logger.info(f"  Category '{cat['name']}' already exists — skipping.")
            name_to_id[cat["name"]] = existing.id
            continue

        new_cat = ProductCategory(name=cat["name"], image_url=cat["image_url"])
        created = await category_repo.create(new_cat)
        name_to_id[created.name] = created.id
        logger.info(f"  Created category '{created.name}'  (id={created.id})")

    return name_to_id


# ---------------------------------------------------------------------------
# Step 3: products
# ---------------------------------------------------------------------------

async def _seed_products(
    product_repo: ProductRepository,
    name_to_category_id: dict[str, UUID],
    products_per_category: int,
    logger,
) -> list[Product]:
    """
    Insert fake products for every category.
    Returns all relevant Product ORM objects (created + pre-existing).
    """
    result: list[Product] = []

    for cat_name, category_id in name_to_category_id.items():
        pool = FAKE_PRODUCTS_BY_CATEGORY.get(cat_name, [])
        if not pool:
            logger.warning(f"  No fake product definitions for '{cat_name}' — skipping.")
            continue

        # Cycle the pool if products_per_category > len(pool)
        chosen = (pool * ((products_per_category // len(pool)) + 1))[:products_per_category]

        for name, brand, description in chosen:
            existing = await product_repo.get_by_field("name", name)
            if existing:
                logger.info(f"    Product '{name}' already exists — skipping.")
                result.append(existing)
                continue

            quantity = random.randint(0, 200)
            price = Decimal(str(round(random.uniform(4.99, 999.99), 2)))

            new_product = Product(
                name=name,
                description=description,
                category_id=category_id,
                brand=brand.lower(),
                quantity=quantity,
                price=price,
                in_stock=quantity > 0,
            )
            product = await product_repo.create(new_product)
            result.append(product)
            logger.info(
                f"    Created '{product.name}'  "
                f"(price={product.price}, qty={product.quantity}, id={product.id})"
            )

    return result


# ---------------------------------------------------------------------------
# Step 4: images (optional)
# ---------------------------------------------------------------------------

async def _seed_images(
    image_repo: ProductImageRepository,
    products: list[Product],
    logger,
) -> None:
    """Attach 2-3 placeholder images to every product that has none yet."""
    for product in products:
        existing = await image_repo.get_many_by_field("product_id", product.id)
        if existing:
            logger.info(f"    Images for '{product.name}' already exist — skipping.")
            continue

        num_images = random.randint(2, 3)
        colours = random.sample(_COLOUR_MAP, min(num_images, len(_COLOUR_MAP)))

        for colour_name, colour_code in colours:
            hex_colour = colour_code.lstrip("#")
            url = (
                f"https://placehold.co/800x600/{hex_colour}/white"
                f"?text={product.name.replace(' ', '+')}"
            )
            await image_repo.create(
                ProductImage(
                    product_id=product.id,
                    image_url=url,
                    image_color=colour_name,
                    image_color_code=colour_code,
                )
            )

        logger.info(f"    Added {num_images} image(s) to '{product.name}'")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def seed_database(
    products_per_category: int = 5,
    with_images: bool = False,
    clear: bool = False,
) -> None:
    """
    Seed the product-service database with fake categories, products, and
    (optionally) product images.

    This function is **idempotent by default**: records that already exist
    (matched by name) are skipped rather than duplicated.

    Args:
        products_per_category:
            How many products to create per category.  If the built-in pool
            for a category has fewer entries the pool is cycled to fill the
            requested count.  Defaults to 5.
        with_images:
            When True, 2-3 placeholder ``ProductImage`` rows are also created
            for each product that currently has no images.
        clear:
            When True, all existing products and categories are deleted before
            the seed runs.  Use with care in production!
    """
    settings = get_settings()
    logger = setup_logger("seed_fake_products")
    db_manager = _make_db_manager(settings, logger)

    logger.info("=" * 60)
    logger.info("Starting product-service database seed ...")
    logger.info(f"  products_per_category : {products_per_category}")
    logger.info(f"  with_images           : {with_images}")
    logger.info(f"  clear first           : {clear}")
    logger.info("=" * 60)

    async with db_manager.transaction() as session:
        category_repo = CategoryRepository(session)
        product_repo  = ProductRepository(session)
        image_repo    = ProductImageRepository(session)

        if clear:
            logger.info("Clearing existing data ...")
            await _clear_existing_data(category_repo, product_repo, logger)

        logger.info("Seeding categories ...")
        name_to_id = await _seed_categories(category_repo, logger)
        logger.info(f"Categories done: {len(name_to_id)} available.")

        logger.info("Seeding products ...")
        products = await _seed_products(product_repo, name_to_id, products_per_category, logger)
        logger.info(f"Products done: {len(products)} available.")

        if with_images:
            logger.info("Seeding product images ...")
            await _seed_images(image_repo, products, logger)
            logger.info("Product images done.")

    await db_manager.close()
    logger.info("=" * 60)
    logger.info("Seed complete!")
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed the Product-Service database with fake products.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--products-per-category",
        type=int,
        default=5,
        metavar="N",
        help="Number of products to create per category (default: 5).",
    )
    parser.add_argument(
        "--with-images",
        action="store_true",
        default=False,
        help="Also create placeholder ProductImage rows for each product.",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        default=False,
        help="Delete ALL existing products and categories before seeding.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(
        seed_database(
            products_per_category=args.products_per_category,
            with_images=args.with_images,
            clear=args.clear,
        )
    )
