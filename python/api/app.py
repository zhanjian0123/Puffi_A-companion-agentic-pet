from fastapi import FastAPI

from api.routes.chat import router as chat_router
from api.routes.health import router as health_router
from api.routes.knowledge import router as knowledge_router
from api.routes.tools import router as tools_router


def create_app() -> FastAPI:
    app = FastAPI(title="AI Pet Agent Service", version="0.1.0")
    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(knowledge_router)
    app.include_router(tools_router)
    return app
