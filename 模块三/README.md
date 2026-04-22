# 时序守望 - Agent 中枢调度模块

> 独居老人安全守护系统后端服务，负责报警接收、智能外呼、工单派发全流程处理。

## 项目概述

本模块为「时序守望」系统的核心调度中枢，接收来自算法模块的预警信号，驱动 Agent 执行语音外呼、家属确认、超时自动派单等业务流程。

## 技术栈

| 分类 | 技术 |
|------|------|
| Web 框架 | FastAPI 0.104.1 |
| ASGI 服务器 | Uvicorn 0.24.0 |
| 数据库 ORM | SQLAlchemy 2.0.23 |
| MySQL 驱动 | PyMySQL 1.1.0 |
| 定时任务 | APScheduler 3.10.4 |
| 数据验证 | Pydantic 2.5.0 |

## 数据模型

### Elder（老人）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| name | String(50) | 姓名 |
| family_phone | String(20) | 家属联系电话 |
| community_id | Integer | 所属社区/网格员 ID |
| sensor_id | String(50) | 关联传感器 ID（唯一） |
| created_at | DateTime | 创建时间 |

### AlertRecord（报警记录）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| elder_id | Integer | 关联老人 ID |
| level | Enum | 预警级别（GREEN/YELLOW/RED） |
| status | Enum | 处理状态（PENDING/CALLING/WAITING_CONFIRM/DISPATCHED/RESOLVED） |
| sensor_id | String(50) | 触发传感器 ID |
| source_alert_id | String(100) | 算法模块原始报警 ID |
| notes | String(255) | 报警描述 |
| triggered_at | DateTime | 触发时间 |
| call_started_at | DateTime | 外呼开始时间 |
| call_ended_at | DateTime | 外呼结束时间 |
| confirmed_at | DateTime | 家属确认时间 |
| dispatch_deadline | DateTime | 超时派单截止时间 |

### WorkOrder（工单）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| alert_id | Integer | 关联报警 ID |
| community_id | Integer | 指派网格员 ID |
| description | String(255) | 工单描述 |
| status | String(20) | 状态（pending/accepted/completed） |
| created_at | DateTime | 创建时间 |

## 预警流程

```
算法检测到异常（RED/YELLOW）
         ↓
AlertRecord 入库，状态=PENDING
         ↓
┌─────────────────────────────────┐
│  RED 预警：启动 Agent 应急流程    │
│  1. 状态 → CALLING              │
│  2. 语音外呼家属（模拟/真实）     │
│  3a. 接通 → WAITING_CONFIRM     │
│  3b. 未接通 → 直接 DISPATCHED   │
│  4. 等待5分钟家属确认            │
│  5a. 确认 → RESOLVED            │
│  5b. 超时 → DISPATCHED + 派单   │
└─────────────────────────────────┘
         ↓
┌─────────────────────────────────┐
│  YELLOW 预警：                  │
│  入库后保持 PENDING             │
│  等待家属主动确认 → RESOLVED    │
└─────────────────────────────────┘
```

## API 端点

### 报警相关

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/alert/from-detection` | 接收算法模块预警信号 |
| POST | `/api/alert/confirm` | 家属确认报警（含红/黄分级） |
| GET | `/api/alert/{alert_id}` | 查询报警详情 |
| GET | `/api/alert/{alert_id}/timeline` | 获取报警处理时间轴 |

### 老人相关

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/elder/add` | 添加老人信息（测试用） |
| GET | `/api/elders/status` | 获取所有老人状态（供大屏使用） |

### 工单相关

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/work_order/{work_order_id}/complete` | 网格员完成工单 |

## 配置说明

### 数据库连接（database.py）

```python
DATABASE_URL = "mysql+pymysql://root:123456@localhost:3306/temporal_watch?charset=utf8mb4"
```

> ⚠️ 生产环境请勿明文存储密码，建议使用环境变量或配置文件。

### 外呼模式（main.py）

```python
USE_MOCK_CALL = True  # 演示设为 True，真实部署改为 False
```

- `True`：模拟外呼（90% 接通率，2秒延迟）
- `False`：接入真实云通讯服务

### CORS 配置

已配置允许所有来源跨域，生产环境建议限制 `allow_origins`。

## 快速启动

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python main.py

# 或使用 uvicorn 直接启动
uvicorn main:app --host 0.0.0.0 --port 8000
```

服务启动后访问 `http://localhost:8000/docs` 查看交互式 API 文档。

## 数据库初始化

模型定义中已包含 `Base.metadata.create_all(bind=engine)`，首次启动会自动创建表结构。

## 项目结构

```
model3.3/
├── main.py           # FastAPI 应用主文件（含所有 API 端点）
├── models.py         # SQLAlchemy 数据模型定义
├── database.py       # 数据库连接配置
├── schemas.py        # Pydantic 请求/响应模型
└── requirements.txt  # Python 依赖列表
```