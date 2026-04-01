from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any
from ..models.metadata import BatchUpdate, BatchResult, UpdateField
from ..services.metadata_service import (
    apply_change_to_cache, add_pending_change, get_pending_changes,
    commit_pending_changes, get_metadata, load_metadata, export_metadata_backup
)
from ..services.audit_service import log_change
from ..core.auth import get_current_user
from ..core.config import settings
from datetime import datetime

router = APIRouter(prefix="/api/batch", tags=["batch"])


@router.post("/update")
def batch_update(batch: BatchUpdate, user=Depends(get_current_user)):
    """Aplica multiplas atualizacoes em lote"""
    if settings.READ_ONLY_MODE:
        raise HTTPException(403, "Sistema em modo somente leitura")

    meta = get_metadata() or load_metadata()

    success_count = 0
    failed_count = 0
    errors = []

    for update in batch.updates:
        # Buscar valor antigo
        old_value = None
        for t in meta.get("tables", []):
            if t["id"] == update.tableId:
                all_objs = t.get("columns", []) + t.get("measures", []) + t.get("hierarchies", [])
                for obj in all_objs:
                    if obj["id"] == update.objectId:
                        old_value = obj.get(update.field)
                        break

        ok = apply_change_to_cache(
            object_type=update.objectType,
            object_id=update.objectId,
            table_id=update.tableId,
            field=update.field,
            value=update.value
        )

        if ok:
            add_pending_change({
                "objectType": update.objectType,
                "objectId": update.objectId,
                "tableId": update.tableId,
                "field": update.field,
                "value": update.value,
                "oldValue": old_value
            })
            log_change(
                username=user.username,
                action="batch_update",
                object_type=update.objectType,
                object_id=update.objectId,
                field=update.field,
                old_value=old_value,
                new_value=update.value
            )
            success_count += 1
        else:
            failed_count += 1
            errors.append(f"Objeto nao encontrado: {update.objectId}")

    result = BatchResult(
        success=success_count,
        failed=failed_count,
        errors=errors,
        appliedAt=datetime.utcnow()
    )

    # Se applyImmediately, commit agora
    if batch.applyImmediately:
        commit_result = commit_pending_changes()
        return {**result.model_dump(), "committed": commit_result}

    return result.model_dump()


@router.post("/hide")
def batch_hide(
    ids: List[str],
    table_id: str = Query(...),
    object_type: str = Query(...),
    user=Depends(get_current_user)
):
    """Oculta multiplos objetos"""
    if settings.READ_ONLY_MODE:
        raise HTTPException(403, "Modo somente leitura")

    updates = [
        UpdateField(objectType=object_type, objectId=oid, tableId=table_id, field="hidden", value=True)
        for oid in ids
    ]
    return batch_update(BatchUpdate(updates=updates, applyImmediately=False), user)


@router.post("/show")
def batch_show(
    ids: List[str],
    table_id: str = Query(...),
    object_type: str = Query(...),
    user=Depends(get_current_user)
):
    """Mostra multiplos objetos"""
    if settings.READ_ONLY_MODE:
        raise HTTPException(403, "Modo somente leitura")

    updates = [
        UpdateField(objectType=object_type, objectId=oid, tableId=table_id, field="hidden", value=False)
        for oid in ids
    ]
    return batch_update(BatchUpdate(updates=updates, applyImmediately=False), user)


@router.post("/set-display-folder")
def batch_set_folder(
    ids: List[str],
    table_id: str = Query(...),
    object_type: str = Query(...),
    folder: str = Query(...),
    user=Depends(get_current_user)
):
    """Altera display folder em lote"""
    if settings.READ_ONLY_MODE:
        raise HTTPException(403, "Modo somente leitura")

    updates = [
        UpdateField(objectType=object_type, objectId=oid, tableId=table_id, field="displayFolder", value=folder)
        for oid in ids
    ]
    return batch_update(BatchUpdate(updates=updates, applyImmediately=False), user)


@router.post("/set-description")
def batch_set_description(
    ids: List[str],
    table_id: str = Query(...),
    object_type: str = Query(...),
    description: str = Query(...),
    user=Depends(get_current_user)
):
    """Altera descricao em lote"""
    if settings.READ_ONLY_MODE:
        raise HTTPException(403, "Modo somente leitura")

    updates = [
        UpdateField(objectType=object_type, objectId=oid, tableId=table_id, field="description", value=description)
        for oid in ids
    ]
    return batch_update(BatchUpdate(updates=updates, applyImmediately=False), user)
