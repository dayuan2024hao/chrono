功能：多老人数据隔离、自动生成监护日报、用水 / 用电 / 门磁 / 活动统计、异常判断、阿里云 AI 问答、已开启跨域
安装依赖：pip install flask flask-cors requests
启动命令：python app.py
接口说明：
上报数据：POST /api/receive_event
老人列表：GET /api/elder_list
单个日报：GET /api/get_result?name = 张爷爷
全部日报：GET /api/get_result
AI 问答：POST /api/ai_chat
配置：替换 API_KEY 为阿里云密钥，知识库 txt 放同级目录
规则：老人名称 = XX 爷爷 / XX 奶奶，识别关键词：用水、用电、门磁、活动、异常、跌倒
注意：数据存在内存，重启服务会清空
