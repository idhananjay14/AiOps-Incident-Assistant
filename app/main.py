import logging
import time
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Task
from app.schemas import TaskCreate, TaskResponse, TaskUpdate

from app.config import settings
from app.logging import configure_logging


app = FastAPI(
    title="AIOps Incident Assistant",
    version="0.1.0",
)


configure_logging()
logger = logging.getLogger("app")


def apply_failure_mode() -> None:
    if settings.failure_mode == "high_latency":
        time.sleep(3)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id

    start_time = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

    logger.info(
        "request completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
        },
    )

    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "environment": settings.app_env,
    }


@app.post("/tasks", response_model=TaskResponse, status_code=201)
def create_task(task: TaskCreate, db: Session = Depends(get_db)) -> Task:
    apply_failure_mode()
    db_task = Task(
        title=task.title,
        description=task.description,
    )

    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    return db_task

@app.get("/tasks", response_model=list[TaskResponse])
def list_tasks(db: Session = Depends(get_db)) -> list[Task]:
    apply_failure_mode()
    return db.query(Task).order_by(Task.id).all()

@app.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)) -> Task:
    apply_failure_mode()
    task = db.get(Task, task_id)

    if task is None:

        raise HTTPException(status_code=404, detail="Task not found")

    return task

@app.put("/tasks/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    task_update: TaskUpdate,
    db: Session = Depends(get_db),
) -> Task:
    apply_failure_mode()

    task = db.get(Task, task_id)

    if task is None:

        raise HTTPException(status_code=404, detail="Task not found")

    update_data = task_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)

    return task

@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)) -> None:
    apply_failure_mode()
    task = db.get(Task, task_id)

    if task is None:

        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(task)
    db.commit()
