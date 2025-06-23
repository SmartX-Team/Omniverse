from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .core.logger import logger
from .api import health, websocket

# FastAPI 앱 생성
app = FastAPI(
    title="Omni Web Gateway",
    description="WebSocket relay server between Omniverse and Web UI",
    version="1.0.0",
    debug=settings.debug
)

# CORS 미들웨어 추가 - 테스트용으로 모든 오리진 허용
if settings.cors_allow_all:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 모든 오리진 허용
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # 나중에 프로덕션용 CORS 설정을 여기에 추가인데 어차피 아무도 안할듯 
    pass

# 라우터 등록
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(websocket.router, tags=["websocket"])


@app.on_event("startup")
async def startup_event():
    logger.info("Omni Web Gateway Server Starting...")
    logger.info(f"Server will run on {settings.host}:{settings.port}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"CORS: {'All origins allowed (TESTING MODE)' if settings.cors_allow_all else 'Restricted'}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Omni Web Gateway Server Shutting Down...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )