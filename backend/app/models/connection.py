from pydantic import BaseModel
from typing import Optional, List
from enum import Enum


class ConnectionMode(str, Enum):
    LOCAL = "LOCAL"
    REMOTE = "REMOTE"


class ConnectionRequest(BaseModel):
    mode: ConnectionMode
    serverUrl: Optional[str] = None
    workspaceName: Optional[str] = None
    modelName: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


class ConnectionStatus(BaseModel):
    connected: bool
    serverUrl: Optional[str] = None
    databaseName: Optional[str] = None
    modelName: Optional[str] = None
    connectionId: Optional[str] = None
    connectedAt: Optional[str] = None
    errorMessage: Optional[str] = None
    demo: bool = False


class WorkspaceInfo(BaseModel):
    id: str
    name: str
    models: List[str] = []
