from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = "sqlite:///./color_temp.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class ColorGroup(Base):
    __tablename__ = "color_groups"

    group_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=True)
    target_color_temp = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
    heartbeat_logs = relationship("HeartbeatLog", back_populates="group", cascade="all, delete-orphan")


class GroupMember(Base):
    __tablename__ = "group_members"

    member_id = Column(String, primary_key=True, index=True)
    group_id = Column(String, ForeignKey("color_groups.group_id"), primary_key=True)
    client_ip = Column(String)
    client_port = Column(Integer)
    current_color_temp = Column(Float, nullable=True)
    last_heartbeat = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    group = relationship("ColorGroup", back_populates="members")


class HeartbeatLog(Base):
    __tablename__ = "heartbeat_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(String, ForeignKey("color_groups.group_id"))
    member_id = Column(String, nullable=False)
    color_temp = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    group = relationship("ColorGroup", back_populates="heartbeat_logs")


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
