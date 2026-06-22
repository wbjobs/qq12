from typing import List
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from database import init_db, get_db
from schemas import (
    GroupCreate, GroupUpdate, GroupStatus,
    HeartbeatLogResponse
)
import services

app = FastAPI(title="色温组管理 API", version="1.0.0")

_udp_service = None


def set_udp_service(service):
    global _udp_service
    _udp_service = service


@app.on_event("startup")
async def startup():
    init_db()


@app.get("/", tags=["root"])
def root():
    return {
        "service": "Color Temperature Group Management API",
        "version": "1.0.0",
        "endpoints": {
            "groups": "/api/v1/groups",
            "docs": "/docs"
        }
    }


@app.get("/api/v1/groups", response_model=List[GroupStatus], tags=["groups"])
def list_all_groups(db: Session = Depends(get_db)):
    return services.list_groups(db)


@app.post("/api/v1/groups", response_model=GroupStatus, tags=["groups"])
def create_group(group_data: GroupCreate, db: Session = Depends(get_db)):
    return services.create_group(db, group_data)


@app.get("/api/v1/groups/{group_id}", response_model=GroupStatus, tags=["groups"])
def get_group(group_id: str, db: Session = Depends(get_db)):
    status = services.get_group_status(db, group_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Group '{group_id}' not found")
    return status


@app.put("/api/v1/groups/{group_id}", response_model=GroupStatus, tags=["groups"])
def update_group(group_id: str, update_data: GroupUpdate, db: Session = Depends(get_db)):
    status = services.update_group(db, group_id, update_data)
    if not status:
        raise HTTPException(status_code=404, detail=f"Group '{group_id}' not found")
    return status


@app.delete("/api/v1/groups/{group_id}", tags=["groups"])
def delete_group(group_id: str, db: Session = Depends(get_db)):
    success = services.delete_group(db, group_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Group '{group_id}' not found")
    return {"success": True, "message": f"Group '{group_id}' deleted"}


@app.delete("/api/v1/groups/{group_id}/members/{member_id}", tags=["members"])
def kick_member(group_id: str, member_id: str, db: Session = Depends(get_db)):
    success = services.kick_member(db, group_id, member_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Member '{member_id}' not found in group '{group_id}'"
        )
    return {"success": True, "message": f"Member '{member_id}' kicked from group '{group_id}'"}


@app.post("/api/v1/groups/{group_id}/target-temp", response_model=GroupStatus, tags=["groups"])
def set_target_temperature(
    group_id: str,
    target_temp: float,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    if target_temp < 1000 or target_temp > 10000:
        raise HTTPException(
            status_code=400,
            detail="Color temperature must be between 1000K and 10000K"
        )

    status = services.set_target_temp(db, group_id, target_temp)
    if not status:
        raise HTTPException(status_code=404, detail=f"Group '{group_id}' not found")

    if _udp_service:
        background_tasks.add_task(_udp_service.notify_target_temp, group_id, target_temp)

    return status


@app.get(
    "/api/v1/groups/{group_id}/heartbeat-logs",
    response_model=List[HeartbeatLogResponse],
    tags=["groups"]
)
def get_heartbeat_logs(group_id: str, limit: int = 100, db: Session = Depends(get_db)):
    group = services.get_group_status(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail=f"Group '{group_id}' not found")

    logs = services.get_heartbeat_logs(db, group_id, limit)
    return logs
