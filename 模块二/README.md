1、核心功能
双重检测机制：
红色预警（规则引擎）：基于硬性阈值（如连续 2 小时无活动），实时检测紧急状况。
黄色预警（机器学习）：基于 Isolation Forest 算法，学习用户长期行为基线，识别偏离日常习惯的异常模式。
异步高并发处理：基于 FastAPI 构建，支持高吞吐量的数据接入与后台异步检测，确保系统低延迟。
智能预警抑制：内置冷却时间机制（红色 10s / 黄色 30s），防止同一异常重复报警，减少干扰。
自动模型迭代：系统自动缓存特征数据，并每隔 24 小时自动重训练模型，适应老人生活习惯的季节性变化。

2、环境依赖
Python 3.7+
依赖库：fastapi, uvicorn, httpx, pandas, numpy, scikit-learn, pydantic

3、安装依赖
pip install fastapi uvicorn httpx pandas numpy scikit-learn pydantic

4、配置参数
在代码顶部修改以下关键配置：
DOWNSTREAM_URL：下游模块（如 3.3 报警模块）的接收地址。
SERVICE_PORT：本服务监听端口（默认 8001）。
RED_NO_ACTIVITY_HOURS：红色预警触发阈值（默认 2 小时）。
MODEL_RETRAIN_HOURS：模型自动重训练周期（默认 24 小时）。
