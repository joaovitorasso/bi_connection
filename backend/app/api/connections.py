from fastapi import APIRouter, HTTPException, Depends
from ..models.connection import ConnectionRequest, ConnectionStatus
from ..services.connection_service import get_tom_service, get_connection_info, set_connection_info, reset_connection
from ..services.metadata_service import clear_metadata
from ..core.auth import get_current_user
from datetime import datetime

router = APIRouter(prefix="/api/connections", tags=["connections"])


@router.get("/status")
def get_status():
    info = get_connection_info()
    if not info:
        return {"connected": False}
    return info


@router.post("/connect")
def connect(req: ConnectionRequest, user=Depends(get_current_user)):
    tom = get_tom_service()
    try:
        if req.mode == "LOCAL":
            result = tom.connect_local()
        elif req.mode == "REMOTE":
            result = tom.connect_remote(
                workspace=req.workspaceName or "",
                model=req.modelName or "",
                username=req.username,
                password=req.password
            )
        else:
            raise HTTPException(400, "Modo de conexao invalido")

        result["connectedAt"] = datetime.utcnow().isoformat()
        result["mode"] = req.mode
        set_connection_info(result)
        clear_metadata()
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Falha na conexao: {str(e)}")


@router.post("/disconnect")
def disconnect(user=Depends(get_current_user)):
    reset_connection()
    clear_metadata()
    return {"disconnected": True}


@router.get("/databases")
def list_databases(user=Depends(get_current_user)):
    tom = get_tom_service()
    return {"databases": tom.get_databases()}
