from sqlalchemy import Column, Integer, String, DateTime, Enum, Boolean, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()

class AlertLevel(str, enum.Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"

class AlertStatus(str, enum.Enum):
    PENDING = "pending"          # 刚触发，等待Agent处理
    CALLING = "calling"          # 正在外呼家属
    WAITING_CONFIRM = "waiting_confirm"  # 已外呼，等待家属确认
    CONFIRMED = "confirmed"      # 家属已确认
    DISPATCHED = "dispatched"    # 已派单
    RESOLVED = "resolved"        # 已处理完毕

class Elder(Base):
    __tablename__ = "elders"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    # phone = Column(String(20))
    family_phone = Column(String(20), nullable=False)
    community_id = Column(Integer, nullable=False)
    sensor_id = Column(String(50), unique=True, nullable=True)   # 新增：传感器ID，如 "6632"
    created_at = Column(DateTime, server_default=func.now())

class AlertRecord(Base):
    __tablename__ = "alert_records"
    id = Column(Integer, primary_key=True, index=True)
    elder_id = Column(Integer, ForeignKey("elders.id"))
    level = Column(Enum(AlertLevel), default=AlertLevel.RED)
    status = Column(Enum(AlertStatus), default=AlertStatus.PENDING)
    triggered_at = Column(DateTime, server_default=func.now())
    call_started_at = Column(DateTime, nullable=True)
    call_ended_at = Column(DateTime, nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    dispatch_deadline = Column(DateTime, nullable=True)  # 超时派单时间点
    notes = Column(String(255))
    source_alert_id = Column(String(100), nullable=True)   # 算法模块的 alert_id
    sensor_id = Column(String(50), nullable=True) 

class WorkOrder(Base):
    __tablename__ = "work_orders"
    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alert_records.id"))
    community_id = Column(Integer, nullable=False)       # 指派网格员ID
    description = Column(String(255))
    created_at = Column(DateTime, server_default=func.now())
    status = Column(String(20), default="pending")       # pending / accepted / completed
