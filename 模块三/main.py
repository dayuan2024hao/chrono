from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import asyncio
import random
import logging
import uvicorn


from fastapi.middleware.cors import CORSMiddleware

from database import SessionLocal, engine
from models import Base, Elder, AlertRecord, WorkOrder, AlertStatus, AlertLevel
from schemas import ConfirmRequest
from pydantic import BaseModel
from typing import List


# ---------- 配置日志 ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ---------- 请求模型 ----------
class ElderAddRequest(BaseModel):
    name: str
    family_phone: str
    community_id: int
    sensor_id: str = None   # 可选

# 定义算法模块的请求体结构
class AlgorithmAlertItem(BaseModel):
    alert_id: str
    alert_level: str          # "RED" / "YELLOW" / "GREEN"
    sensor_id: str
    sensor_name: str
    anomaly_type: str
    timestamp: str
    detected_value: float
    baseline_value: float
    confidence: float
    description: str
    recommendations: List[str]

class AlgorithmAlertRequest(BaseModel):
    status: int
    message: str
    timestamp: str
    alerts: List[AlgorithmAlertItem]

app = FastAPI(title="时序守望 - Agent中枢调度模块")

# 👇 我只加了这一段跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 创建表（实际生产建议用Alembic迁移）
Base.metadata.create_all(bind=engine)

# ---------- 数据库会话依赖 ----------
def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

# ---------- 外呼功能配置 ----------
USE_MOCK_CALL = True  # 比赛演示设为 True，真实部署改为 False

async def make_voice_call(phone_number: str, message: str):
    """
    语音外呼接口。
    当 USE_MOCK_CALL = True 时，使用模拟逻辑；
    否则调用真实云通讯服务（需补充 SDK 代码）。
    """
    if USE_MOCK_CALL:
        logger.info(f"[模拟外呼] 拨打电话至 {phone_number}，内容：{message[:30]}...")
        await asyncio.sleep(2)  # 模拟网络延迟
        # 模拟 90% 接通率
        if random.random() < 0.9:
            call_id = f"call_{datetime.now().timestamp()}"
            logger.info(f"[模拟外呼] 呼叫成功，call_id: {call_id}")
            return {"success": True, "call_id": call_id}
        else:
            logger.warning("[模拟外呼] 呼叫失败")
            return {"success": False, "call_id": None}
    else:
        # TODO: 替换为真实云通讯 API 调用
        logger.warning("真实外呼功能未实现，当前为 pass")
        return {"success": False, "call_id": None}

# ---------- 自动派单（内部调用） ----------
async def create_work_order(alert_id: int, community_id: int, description: str, db: Session):
    """创建工单并存入数据库"""
    work_order = WorkOrder(
        alert_id=alert_id,
        community_id=community_id,
        description=description,
        status="pending"
    )
    db.add(work_order)
    db.commit()
    db.refresh(work_order)
    logger.info(f"[工单创建] 工单ID {work_order.id} 已分配给网格员 {community_id}")
    return work_order

# ---------- 后台任务：Agent 应急全流程 ----------
async def agent_emergency_flow(alert_id: int, elder_id: int, db: Session = None):
    """
    后台异步任务，不阻塞 HTTP 响应。
    流程：
        1. 标记状态为 CALLING
        2. 调用外呼 API
        3. 成功则进入 WAITING_CONFIRM，并设置 5 分钟超时
        4. 失败则直接派单
    
    参数:
        db: 可选的数据库会话。若为 None 则内部自动创建和关闭，避免响应结束后会话失效。
    """
    # 如果没有传入 db，则自己创建一个新的会话
    if db is None:
        db = SessionLocal()
        should_close = True
    else:
        should_close = False

    try:
        # 获取老人信息
        elder = db.query(Elder).filter(Elder.id == elder_id).first()
        if not elder:
            logger.error(f"[Agent] 老人ID {elder_id} 不存在，任务终止")
            return

        alert = db.query(AlertRecord).filter(AlertRecord.id == alert_id).first()
        if not alert:
            logger.error(f"[Agent] 报警ID {alert_id} 不存在，任务终止")
            return

        # 1. 更新状态为呼叫中
        alert.status = AlertStatus.CALLING
        alert.call_started_at = datetime.now()
        db.commit()

        # 2. 调用外呼 API
        message = f"您好，这里是时序守望关怀系统。检测到{elder.name}家中出现{alert.notes}状况，请立即查看或联系社区。"
        result = await make_voice_call(elder.family_phone, message)

        if result["success"]:
            # 外呼成功，进入等待确认状态
            alert.status = AlertStatus.WAITING_CONFIRM
            alert.call_ended_at = datetime.now()
            alert.dispatch_deadline = datetime.now() + timedelta(minutes=5)
            db.commit()
            logger.info(f"[Agent] 报警ID {alert_id} 外呼成功，等待家属确认，超时时间：{alert.dispatch_deadline}")
        else:
            # 外呼失败，直接派单
            alert.status = AlertStatus.DISPATCHED
            alert.notes = "外呼失败，直接派单"
            db.commit()
            await create_work_order(
                alert_id,
                elder.community_id,
                f"紧急！{elder.name}家中异常，且家属电话未接通。",
                db
            )
            logger.warning(f"[Agent] 报警ID {alert_id} 外呼失败，已直接派单")
    finally:
        if should_close:
            db.close()

# ---------- API 端点 ----------
@app.post("/api/alert/from-detection")
async def receive_detection_alerts(
    request: AlgorithmAlertRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    processed_red = 0
    processed_yellow = 0
    for alert_item in request.alerts:
        # 处理红色预警
        if alert_item.alert_level == "RED":
            elder = db.query(Elder).filter(Elder.sensor_id == alert_item.sensor_id).first()
            if not elder:
                logger.error(f"未找到 sensor_id={alert_item.sensor_id} 对应的老人，跳过预警 {alert_item.alert_id}")
                continue
            alert = AlertRecord(
                elder_id=elder.id,
                level=AlertLevel.RED,
                status=AlertStatus.PENDING,
                notes=alert_item.description,
                source_alert_id=alert_item.alert_id,
                sensor_id=alert_item.sensor_id
            )
            db.add(alert)
            db.commit()
            db.refresh(alert)
            background_tasks.add_task(agent_emergency_flow, alert.id, elder.id, None)
            processed_red += 1

        # 处理黄色预警（初始状态为 PENDING，等待家属确认）
        elif alert_item.alert_level == "YELLOW":
            elder = db.query(Elder).filter(Elder.sensor_id == alert_item.sensor_id).first()
            if not elder:
                logger.error(f"未找到 sensor_id={alert_item.sensor_id} 对应的老人，跳过黄色预警 {alert_item.alert_id}")
                continue
            alert = AlertRecord(
                elder_id=elder.id,
                level=AlertLevel.YELLOW,
                status=AlertStatus.PENDING,   # 等待确认
                notes=alert_item.description,
                source_alert_id=alert_item.alert_id,
                sensor_id=alert_item.sensor_id
            )
            db.add(alert)
            db.commit()
            logger.info(f"黄色预警已记录: {alert_item.alert_id}, 老人: {elder.name}")
            processed_yellow += 1
        else:
            logger.info(f"忽略其他级别预警: {alert_item.alert_level}")

    logger.info(f"批量处理完成 - 红色: {processed_red}, 黄色: {processed_yellow}")
    return {"code": 0, "message": f"已处理红色{processed_red}条, 黄色{processed_yellow}条"}

@app.post("/api/alert/confirm")
async def family_confirm(request: ConfirmRequest, db: Session = Depends(get_db)):
    """
    统一确认接口：支持红色和黄色预警。
    - 红色预警：需要状态为 WAITING_CONFIRM
    - 黄色预警：需要状态为 PENDING
    确认后将状态改为 RESOLVED，表示已解决。
    """
    alert = db.query(AlertRecord).filter(AlertRecord.id == request.alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="报警记录不存在")

    if alert.level == AlertLevel.RED:
        if alert.status != AlertStatus.WAITING_CONFIRM:
            raise HTTPException(status_code=400, detail="当前红色预警状态不可确认")
    elif alert.level == AlertLevel.YELLOW:
        if alert.status != AlertStatus.PENDING:
            raise HTTPException(status_code=400, detail="当前黄色预警状态不可确认")
    else:
        raise HTTPException(status_code=400, detail="不支持的报警级别")

    alert.status = AlertStatus.RESOLVED
    alert.confirmed_at = datetime.now()
    db.commit()
    logger.info(f"[API] 报警ID {request.alert_id} 已被家属确认并解决")
    return {"code": 0, "message": "已确认，报警解除"}

@app.post("/api/work_order/{work_order_id}/complete")
async def complete_work_order(work_order_id: int, db: Session = Depends(get_db)):
    """网格员完成工单，将关联报警状态设为 RESOLVED"""
    work_order = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not work_order:
        raise HTTPException(404, "工单不存在")
    work_order.status = "completed"
    alert = db.query(AlertRecord).filter(AlertRecord.id == work_order.alert_id).first()
    if alert:
        alert.status = AlertStatus.RESOLVED
    db.commit()
    return {"code": 0, "message": "工单已完成"}

async def _check_timeout_async(db: Session):
    """内部函数：扫描超时报警并派单（供定时任务调用）"""
    now = datetime.now()
    timeout_alerts = db.query(AlertRecord).filter(
        AlertStatus.WAITING_CONFIRM,
        AlertRecord.dispatch_deadline <= now
    ).all()

    dispatched_count = 0
    for alert in timeout_alerts:
        elder = db.query(Elder).filter(Elder.id == alert.elder_id).first()
        if not elder:
            continue

        description = f"独居老人{elder.name}家中出现{alert.notes}状况，家属未在5分钟内确认，请立即上门查看。"
        await create_work_order(alert.id, elder.community_id, description, db)

        alert.status = AlertStatus.DISPATCHED
        alert.notes = "超时未确认，已自动派单"
        db.commit()
        dispatched_count += 1

    logger.info(f"[超时扫描] 处理了 {dispatched_count} 条超时报警")

@app.get("/api/alert/{alert_id}")
async def get_alert_status(alert_id: int, db: Session = Depends(get_db)):
    """查询报警详情，供家属端或大屏使用"""
    alert = db.query(AlertRecord).filter(AlertRecord.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="报警不存在")
    elder = db.query(Elder).filter(Elder.id == alert.elder_id).first()
    return {
        "alert_id": alert.id,
        "elder_name": elder.name,
        "status": alert.status,
        "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None,
        "can_confirm": alert.status == AlertStatus.WAITING_CONFIRM or alert.status == AlertStatus.PENDING
    }

@app.post("/api/elder/add")
async def add_elder(req: ElderAddRequest, db: Session = Depends(get_db)):
    """添加老人信息（测试用）"""
    elder = Elder(
        name=req.name,
        family_phone=req.family_phone,
        community_id=req.community_id,
        sensor_id=req.sensor_id
    )
    db.add(elder)
    db.commit()
    db.refresh(elder)
    logger.info(f"[API] 添加老人：{elder.name}, ID={elder.id}")
    return {"code": 0, "id": elder.id, "name": elder.name}

@app.get("/api/elders/status")
async def get_all_elders_status(db: Session = Depends(get_db)):
    """供社区大屏使用：返回所有老人及其最新报警状态"""
    elders = db.query(Elder).all()
    result = []
    for elder in elders:
        latest_alert = db.query(AlertRecord).filter(
            AlertRecord.elder_id == elder.id
        ).order_by(AlertRecord.triggered_at.desc()).first()
        
        status = "normal"
        alert_level = None
        alert_id = None
        
        if latest_alert:
            alert_id = latest_alert.id
            alert_level = latest_alert.level.value
            
            # 只有未解决的报警才影响状态显示
            if latest_alert.status != AlertStatus.RESOLVED:
                if latest_alert.level == AlertLevel.YELLOW:
                    status = "warning"
                elif latest_alert.level == AlertLevel.RED:
                    status = "danger"
        
        result.append({
            "elder_id": elder.id,
            "name": elder.name,
            "status": status,
            "alert_id": alert_id,
            "alert_level": alert_level,
        })
    return {"code": 0, "data": result}

@app.get("/api/alert/{alert_id}/timeline")
async def get_alert_timeline(alert_id: int, db: Session = Depends(get_db)):
    """获取报警处理时间轴，根据预警级别动态显示"""
    alert = db.query(AlertRecord).filter(AlertRecord.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="报警不存在")

    timeline = []
    # 1. 触发报警 - 根据级别显示不同文字
    if alert.level == AlertLevel.RED:
        event_text = f"系统检测到红色预警，{alert.notes}"
    elif alert.level == AlertLevel.YELLOW:
        event_text = f"系统检测到黄色预警，{alert.notes}"
    else:
        event_text = f"系统检测到{alert.level.value}预警"
    timeline.append({
        "time": alert.triggered_at.isoformat() if alert.triggered_at else None,
        "event": event_text,
        "status": "完成"
    })
    
    # 2. 外呼家属（仅红色预警才可能有外呼记录）
    if alert.call_started_at:
        timeline.append({
            "time": alert.call_started_at.isoformat(),
            "event": "Agent 呼叫家属",
            "status": "已呼叫"
        })
    if alert.call_ended_at:
        event_text = "家属电话接通" if alert.status != AlertStatus.DISPATCHED else "家属电话未接通"
        timeline.append({
            "time": alert.call_ended_at.isoformat(),
            "event": event_text,
            "status": "完成"
        })
    # 3. 家属确认或超时派单（仅红色预警才会有后续流程）
    if alert.confirmed_at:
        timeline.append({
            "time": alert.confirmed_at.isoformat(),
            "event": "家属已确认报警",
            "status": "完成"
        })
    elif alert.status == AlertStatus.DISPATCHED:
        if alert.dispatch_deadline:
            timeline.append({
                "time": alert.dispatch_deadline.isoformat(),
                "event": "超时未确认，系统自动派单",
                "status": "完成"
            })
        work_order = db.query(WorkOrder).filter(WorkOrder.alert_id == alert_id).first()
        if work_order:
            timeline.append({
                "time": work_order.created_at.isoformat() if work_order.created_at else None,
                "event": f"工单已派发给网格员 {work_order.community_id}",
                "status": "处理中"
            })

    return {"alert_id": alert_id, "timeline": timeline}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)