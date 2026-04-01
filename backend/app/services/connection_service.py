from typing import Optional, Dict, Any
from ..services.tom_service import TOMService

# Singleton do servico TOM (uma conexao por vez para MVP)
_tom_service: Optional[TOMService] = None
_connection_info: Dict[str, Any] = {}


def get_tom_service() -> TOMService:
    global _tom_service
    if _tom_service is None:
        _tom_service = TOMService()
    return _tom_service


def get_connection_info() -> Dict[str, Any]:
    return _connection_info


def set_connection_info(info: Dict[str, Any]):
    global _connection_info
    _connection_info = info


def reset_connection():
    global _tom_service, _connection_info
    if _tom_service:
        _tom_service.disconnect()
        _tom_service = None
    _connection_info = {}
