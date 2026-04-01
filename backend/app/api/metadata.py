from fastapi import APIRouter, HTTPException, Depends
from ..services.metadata_service import (
    load_metadata, get_metadata, add_pending_change, apply_change_to_cache,
    get_pending_changes, discard_pending_changes, commit_pending_changes, export_metadata_backup,
    rename_table_in_cache, set_table_hidden_in_cache, delete_table_from_cache
)
from ..services.audit_service import log_change, get_audit_log
from ..core.auth import get_current_user
from ..models.metadata import UpdateField
from typing import Optional

router = APIRouter(prefix="/api/metadata", tags=["metadata"])


@router.get("/")
def get_all_metadata(force_reload: bool = False, user=Depends(get_current_user)):
    try:
        meta = load_metadata(force_reload=force_reload)
        result = {k: v for k, v in meta.items() if k != "_original"}
        return result
    except Exception as e:
        raise HTTPException(500, f"Erro ao carregar metadados: {str(e)}")


@router.get("/tables")
def list_tables(user=Depends(get_current_user)):
    meta = get_metadata() or load_metadata()
    tables = meta.get("tables", [])
    return [{
        "id": t["id"],
        "name": t["name"],
        "description": t["description"],
        "hidden": t["hidden"],
        "columnCount": len(t.get("columns", [])),
        "measureCount": len(t.get("measures", [])),
        "hierarchyCount": len(t.get("hierarchies", []))
    } for t in tables]


@router.get("/tables/{table_id}")
def get_table(table_id: str, user=Depends(get_current_user)):
    meta = get_metadata() or load_metadata()
    for t in meta.get("tables", []):
        if t["id"] == table_id:
            return t
    raise HTTPException(404, "Tabela nao encontrada")


@router.get("/relationships")
def list_relationships(user=Depends(get_current_user)):
    meta = get_metadata() or load_metadata()
    return meta.get("relationships", [])


@router.get("/objects")
def list_all_objects(
    table_id: Optional[str] = None,
    object_type: Optional[str] = None,
    search: Optional[str] = None,
    hidden: Optional[bool] = None,
    user=Depends(get_current_user)
):
    """Lista todos os objetos (colunas, medidas, hierarquias) com filtros"""
    meta = get_metadata() or load_metadata()
    objects = []

    for table in meta.get("tables", []):
        if table_id and table["id"] != table_id:
            continue

        if not object_type or object_type == "column":
            for col in table.get("columns", []):
                obj = {**col, "objectType": "column"}
                if search and search.lower() not in col["name"].lower() and search.lower() not in col.get("description", "").lower():
                    continue
                if hidden is not None and col["hidden"] != hidden:
                    continue
                objects.append(obj)

        if not object_type or object_type == "measure":
            for meas in table.get("measures", []):
                obj = {**meas, "objectType": "measure"}
                if search and search.lower() not in meas["name"].lower() and search.lower() not in meas.get("description", "").lower():
                    continue
                if hidden is not None and meas["hidden"] != hidden:
                    continue
                objects.append(obj)

        if not object_type or object_type == "hierarchy":
            for hier in table.get("hierarchies", []):
                obj = {**hier, "objectType": "hierarchy"}
                if search and search.lower() not in hier["name"].lower():
                    continue
                if hidden is not None and hier["hidden"] != hidden:
                    continue
                objects.append(obj)

    return {"objects": objects, "total": len(objects)}


@router.post("/update")
def update_object(update: UpdateField, user=Depends(get_current_user)):
    """Aplica uma atualizacao ao cache local (pendente)"""
    from ..core.config import settings
    if settings.READ_ONLY_MODE:
        raise HTTPException(403, "Sistema em modo somente leitura")

    # Buscar valor atual para auditoria
    meta = get_metadata()
    old_value = None
    if meta:
        for t in meta.get("tables", []):
            if t["id"] == update.tableId:
                all_objs = t.get("columns", []) + t.get("measures", []) + t.get("hierarchies", [])
                for obj in all_objs:
                    if obj["id"] == update.objectId:
                        old_value = obj.get(update.field)
                        break

    success = apply_change_to_cache(
        object_type=update.objectType,
        object_id=update.objectId,
        table_id=update.tableId,
        field=update.field,
        value=update.value
    )

    if not success:
        raise HTTPException(404, "Objeto nao encontrado")

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
        action="update",
        object_type=update.objectType,
        object_id=update.objectId,
        field=update.field,
        old_value=old_value,
        new_value=update.value
    )

    return {"success": True, "pendingCount": len(get_pending_changes())}


@router.get("/pending")
def get_pending(user=Depends(get_current_user)):
    return {"changes": get_pending_changes(), "count": len(get_pending_changes())}


@router.post("/discard")
def discard_changes(user=Depends(get_current_user)):
    discard_pending_changes()
    return {"discarded": True}


@router.post("/commit")
def commit_changes(user=Depends(get_current_user)):
    from ..core.config import settings
    if settings.READ_ONLY_MODE:
        raise HTTPException(403, "Sistema em modo somente leitura")
    results = commit_pending_changes()
    return results


@router.get("/backup")
def export_backup(user=Depends(get_current_user)):
    return export_metadata_backup()


@router.get("/audit")
def get_audit(limit: int = 100, user=Depends(get_current_user)):
    return {"entries": get_audit_log(limit), "limit": limit}


@router.post("/tables/{table_id}/rename")
def rename_table(table_id: str, new_name: str, user=Depends(get_current_user)):
    """Renomeia tabela (pendente, aplica no commit)."""
    from ..core.config import settings
    if settings.READ_ONLY_MODE:
        raise HTTPException(403, "Sistema em modo somente leitura")

    normalized = (new_name or "").strip()
    if not normalized:
        raise HTTPException(400, "Novo nome da tabela nao pode ser vazio")

    meta = get_metadata() or load_metadata()

    # Valida duplicidade por nome exibido
    for table in meta.get("tables", []):
        if table.get("id") != table_id and table.get("name", "").strip().lower() == normalized.lower():
            raise HTTPException(400, "Ja existe uma tabela com esse nome")

    result = rename_table_in_cache(table_id, normalized)
    if not result:
        raise HTTPException(404, "Tabela nao encontrada")

    add_pending_change({
        "objectType": "table",
        "objectId": table_id,
        "tableId": table_id,
        "field": "name",
        "value": normalized,
        "oldValue": result["oldName"]
    })

    log_change(
        username=user.username,
        action="rename_table",
        object_type="table",
        object_id=table_id,
        field="name",
        old_value=result["oldName"],
        new_value=normalized
    )

    return {"success": True, "tableId": table_id, "oldName": result["oldName"], "newName": normalized}


@router.post("/tables/{table_id}/hidden")
def set_table_hidden(table_id: str, hidden: bool, user=Depends(get_current_user)):
    """Oculta/exibe a tabela e todos os objetos dela (pendente)."""
    from ..core.config import settings
    if settings.READ_ONLY_MODE:
        raise HTTPException(403, "Sistema em modo somente leitura")

    result = set_table_hidden_in_cache(table_id, hidden)
    if not result:
        raise HTTPException(404, "Tabela nao encontrada")

    # Uma unica pendencia para ocultar/exibir todos os objetos da tabela.
    # Isso evita milhares de entradas pendentes e acelera o commit.
    affected_objects = int(result.get("affectedObjects", 0))
    if result["tableOldHidden"] != result["tableNewHidden"] or affected_objects > 0:
        add_pending_change({
            "objectType": "table",
            "objectId": table_id,
            "tableId": table_id,
            "field": "__set_hidden_all__",
            "value": hidden,
            "oldValue": result["tableOldHidden"]
        })

    log_change(
        username=user.username,
        action="set_table_hidden",
        object_type="table",
        object_id=table_id,
        field="hidden",
        old_value=result["tableOldHidden"],
        new_value=hidden,
        extra={"affectedObjects": affected_objects}
    )

    return {
        "success": True,
        "tableId": table_id,
        "hidden": hidden,
        "affectedObjects": affected_objects,
        "pendingCount": len(get_pending_changes())
    }


@router.post("/tables/{table_id}/delete")
def delete_table(table_id: str, user=Depends(get_current_user)):
    """Exclui tabela (pendente, aplica no commit)."""
    from ..core.config import settings
    if settings.READ_ONLY_MODE:
        raise HTTPException(403, "Sistema em modo somente leitura")

    result = delete_table_from_cache(table_id)
    if not result:
        raise HTTPException(404, "Tabela nao encontrada")

    add_pending_change({
        "objectType": "table",
        "objectId": table_id,
        "tableId": table_id,
        "field": "__delete__",
        "value": True,
        "oldValue": result["tableName"]
    })

    log_change(
        username=user.username,
        action="delete_table",
        object_type="table",
        object_id=table_id,
        field="__delete__",
        old_value=result["tableName"],
        new_value="deleted",
        extra={"removedRelationships": len(result["removedRelationships"])}
    )

    return {
        "success": True,
        "tableId": table_id,
        "tableName": result["tableName"],
        "removedRelationships": len(result["removedRelationships"]),
        "pendingCount": len(get_pending_changes())
    }
