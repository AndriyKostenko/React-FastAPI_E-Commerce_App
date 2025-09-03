from datetime import datetime

from faststream import FastStream # type: ignore
from faststream.rabbit import RabbitBroker, RabbitQueue # type: ignore

from shared.shared_instances import logger, settings
from shared.customized_json_response import JSONResponse

"""
The FastStream app (app) will be executed by faststream run via the command line, 
so no manual uvicorn setup is needed.
Don't need to specify host or port, as faststream run doesn't serve HTTP endpoints—it 
connects directly to RabbitMQ

For now its stated in notification-service microservice, but later on can be moved to a separate microservice
"""


# Create the broker and FastStream app
broker = RabbitBroker(settings.RABBITMQ_BROKER_URL)
app = FastStream(broker, title="Notification Consumer Service")

# Define queues and their dead-letter settings
user_events_queue = RabbitQueue("user.events", durable=True, arguments={"x-dead-letter-exchange": "dlx", "x-dead-letter-routing-key": "user.events.dlq"})
notification_events_queue = RabbitQueue("notification.events", durable=True, arguments={"x-dead-letter-exchange": "dlx", "x-dead-letter-routing-key": "notification.events.dlq"})



@app.get("/health", tags=["Health Check"])  
async def health_check():
    """
    A simple health check endpoint to verify that the service is running.
    """
    return JSONResponse(
        content={
            "status": "ok", 
            "timestamp": datetime.now().isoformat(),
            "service": "notification-consumer-service"
        },
        status_code=200,
        headers={"Cache-Control": "no-cache"}
    )
    
    
app.include_router()