from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class MemberBase(BaseModel):
    member_id: str
    current_color_temp: Optional[float] = None
    last_heartbeat: Optional[datetime] = None
    client_ip: Optional[str] = None
    client_port: Optional[int] = None


class MemberInfo(MemberBase):
    pass


class GroupBase(BaseModel):
    group_id: str
    name: Optional[str] = None
    target_color_temp: Optional[float] = None


class GroupCreate(GroupBase):
    pass


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    target_color_temp: Optional[float] = None


class GroupStatus(GroupBase):
    created_at: datetime
    avg_color_temp: Optional[float] = None
    max_temp_diff: Optional[float] = None
    member_count: int
    members: List[MemberInfo] = []

    class Config:
        from_attributes = True


class HeartbeatLogBase(BaseModel):
    member_id: str
    color_temp: float
    timestamp: datetime


class HeartbeatLogResponse(HeartbeatLogBase):
    id: int

    class Config:
        from_attributes = True
