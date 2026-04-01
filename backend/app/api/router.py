from fastapi import APIRouter
from .connections import router as connections_router
from .metadata import router as metadata_router
from .batch import router as batch_router

api_router = APIRouter()
api_router.include_router(connections_router)
api_router.include_router(metadata_router)
api_router.include_router(batch_router)
