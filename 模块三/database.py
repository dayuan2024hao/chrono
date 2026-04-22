from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 请替换为实际MySQL连接字符串
DATABASE_URL = "mysql+pymysql://root:123456@localhost:3306/temporal_watch?charset=utf8mb4"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)