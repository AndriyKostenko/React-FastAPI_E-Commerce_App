from shared.shared_instances import product_service_redis_manager, settings, logger
from service_layer.image_generation_service import ImageGenerationService
from .broker import taskiq_broker


@taskiq_broker.task
async def generate_image_task(job_id: str, prompt: str, style: str) -> None:
    """
    Execute image generation for a submitted job.

    Runs inside the dedicated TaskiQ worker process (Dockerfile.worker).
    Survives API-worker restarts and is retried automatically by the broker
    on failure — unlike FastAPI BackgroundTasks which are in-process and
    lost if the worker crashes mid-generation.
    """
    service = ImageGenerationService(
        settings=settings,
        cache_manager=product_service_redis_manager,
        logger=logger,
    )
    await service.run_job(job_id=job_id, prompt=prompt, style=style)
