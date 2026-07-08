from taskiq.scheduler.scheduler import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource

from tasks.broker import taskiq_broker


# TaskIQ scheduler that reads schedules from task labels.
# Tasks decorated with `@taskiq_broker.task(schedule=[...])` are picked up
# automatically by the LabelScheduleSource.
supplier_task_scheduler = TaskiqScheduler(
    broker=taskiq_broker,
    sources=[LabelScheduleSource(taskiq_broker)],
)
