from fastapi import APIRouter

from app.tasks.voice_tasks import test_voice_task

router = APIRouter(
    prefix="/test",
    tags=["Test"],
)


@router.post("/task")
async def run_test_task():

    task = test_voice_task.delay("Hello from FastAPI")

    return {
        "success": True,
        "task_id": task.id,
        "message": "Task queued successfully.",
    }
