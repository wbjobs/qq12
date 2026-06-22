from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from database import ColorGroup, GroupMember, HeartbeatLog
from schemas import GroupCreate, GroupUpdate, GroupStatus, MemberInfo


def _kahan_sum(numbers: List[float]) -> float:
    total = 0.0
    compensation = 0.0
    for num in numbers:
        y = num - compensation
        t = total + y
        compensation = (t - total) - y
        total = t
    return total


def _calculate_group_stats(members) -> Tuple[Optional[float], Optional[float]]:
    valid_temps = [m.current_color_temp for m in members if m.current_color_temp is not None]
    if not valid_temps:
        return None, None

    sum_total = _kahan_sum(valid_temps)
    avg_temp = sum_total / len(valid_temps)
    avg_temp = round(avg_temp, 2)

    max_temp = max(valid_temps)
    min_temp = min(valid_temps)
    max_diff = round(max_temp - min_temp, 2)

    return avg_temp, max_diff


def get_group_status(db: Session, group_id: str) -> Optional[GroupStatus]:
    group = db.query(ColorGroup).filter(ColorGroup.group_id == group_id).first()
    if not group:
        return None

    avg_temp, max_diff = _calculate_group_stats(group.members)

    return GroupStatus(
        group_id=group.group_id,
        name=group.name,
        target_color_temp=group.target_color_temp,
        created_at=group.created_at,
        avg_color_temp=avg_temp,
        max_temp_diff=max_diff,
        member_count=len(group.members),
        members=[
            MemberInfo(
                member_id=m.member_id,
                current_color_temp=m.current_color_temp,
                last_heartbeat=m.last_heartbeat,
                client_ip=m.client_ip,
                client_port=m.client_port
            )
            for m in group.members
        ]
    )


def list_groups(db: Session) -> List[GroupStatus]:
    groups = db.query(ColorGroup).all()
    result = []
    for group in groups:
        avg_temp, max_diff = _calculate_group_stats(group.members)
        result.append(GroupStatus(
            group_id=group.group_id,
            name=group.name,
            target_color_temp=group.target_color_temp,
            created_at=group.created_at,
            avg_color_temp=avg_temp,
            max_temp_diff=max_diff,
            member_count=len(group.members),
            members=[
                MemberInfo(
                    member_id=m.member_id,
                    current_color_temp=m.current_color_temp,
                    last_heartbeat=m.last_heartbeat,
                    client_ip=m.client_ip,
                    client_port=m.client_port
                )
                for m in group.members
            ]
        ))
    return result


def create_group(db: Session, group_data: GroupCreate) -> GroupStatus:
    existing = db.query(ColorGroup).filter(ColorGroup.group_id == group_data.group_id).first()
    if existing:
        return get_group_status(db, group_data.group_id)

    group = ColorGroup(
        group_id=group_data.group_id,
        name=group_data.name or group_data.group_id,
        target_color_temp=group_data.target_color_temp
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return get_group_status(db, group.group_id)


def update_group(db: Session, group_id: str, update_data: GroupUpdate) -> Optional[GroupStatus]:
    group = db.query(ColorGroup).filter(ColorGroup.group_id == group_id).first()
    if not group:
        return None

    if update_data.name is not None:
        group.name = update_data.name
    if update_data.target_color_temp is not None:
        group.target_color_temp = update_data.target_color_temp

    db.commit()
    db.refresh(group)
    return get_group_status(db, group_id)


def delete_group(db: Session, group_id: str) -> bool:
    group = db.query(ColorGroup).filter(ColorGroup.group_id == group_id).first()
    if not group:
        return False
    db.delete(group)
    db.commit()
    return True


def kick_member(db: Session, group_id: str, member_id: str) -> bool:
    member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.member_id == member_id
    ).first()
    if not member:
        return False
    db.delete(member)
    db.commit()
    return True


def set_target_temp(db: Session, group_id: str, target_temp: float) -> Optional[GroupStatus]:
    group = db.query(ColorGroup).filter(ColorGroup.group_id == group_id).first()
    if not group:
        return None
    group.target_color_temp = target_temp
    db.commit()
    db.refresh(group)
    return get_group_status(db, group_id)


def get_heartbeat_logs(db: Session, group_id: str, limit: int = 100) -> List[HeartbeatLog]:
    return db.query(HeartbeatLog).filter(
        HeartbeatLog.group_id == group_id
    ).order_by(HeartbeatLog.timestamp.desc()).limit(limit).all()
