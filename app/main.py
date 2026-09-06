from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Task
from app.schemas import TaskCreate, TaskResponse, TaskUpdate

from app.config import settings


app = FastAPI(
    title="AIOps Incident Assistant",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "environment": settings.app_env,
    }


@app.post("/tasks", response_model=TaskResponse, status_code=201)
def create_task(task: TaskCreate, db: Session = Depends(get_db)) -> Task:
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
    return db.query(Task).order_by(Task.id).all()

@app.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)) -> Task:
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
    task = db.get(Task, task_id)

    if task is None:

        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(task)
    db.commit()
