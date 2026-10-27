from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.deps import TOTAL_COUNT_HEADER
from src.api.routes import api_router
from src.config.settings import settings

app = FastAPI(
    title="EZScreen Core API",
    description="Backend Platform API for EZScreen candidate screening and ATS management",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Let the browser read the pagination total on cross-origin deployments.
    expose_headers=[TOTAL_COUNT_HEADER],
)

app.include_router(api_router)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Welcome to EZScreen Core API"}
