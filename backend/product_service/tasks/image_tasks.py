from aiohttp import ClientSession
from shared.shared_instances import product_service_redis_manager, settings, logger
from service_layer.image_generation_service import ImageGenerationService
from service_layer.image_generation_quota import GenerationQuotaService
from service_layer.image_job_store import ImageJobStore
from service_layer.openrouter_client import OpenRouterClient
from service_layer.image_storage_service import ImageStorageService
from .broker import taskiq_broker


@taskiq_broker.task
async def generate_image_task(job_id: str,
							  prompt: str,
							  style: str) -> None:
    """
    Execute image generation for a submitted job.

    Runs inside the dedicated TaskIQ worker process (Dockerfile.worker).
    Survives API-worker restarts and is retried automatically by the broker
    on failure — unlike FastAPI BackgroundTasks which are in-process and
    lost if the worker crashes mid-generation.

    A fresh aiohttp session is opened for each task so the worker process
    does not share connection-pool state with the API process.
    """
    async with ClientSession() as session:
        service = ImageGenerationService(
            openrouter_client=OpenRouterClient(
                session=session,
                settings=settings,
                logger=logger,
            ),
            quota_service=GenerationQuotaService(
                cache_manager=product_service_redis_manager,
                settings=settings,
                logger=logger,
            ),
            job_store=ImageJobStore(
                cache_manager=product_service_redis_manager,
                logger=logger,
            ),
            storage_service=ImageStorageService(logger=logger),
            settings=settings,
            logger=logger,
        )
        await service.run_job(
            job_id=job_id,
            prompt=prompt,
            style=style
        )
