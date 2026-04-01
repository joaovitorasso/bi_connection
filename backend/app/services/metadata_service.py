from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import copy
from collections import OrderedDict

from .connection_service import get_tom_service

# Cache de metadados em memoria (para edicoes pendentes)
_metadata_cache: Optional[Dict[str, Any]] = None
_pending_changes: List[Dict[str, Any]] = []


def load_metadata(force_reload: bool = False) -> Dict[str, Any]:
    global _metadata_cache
    if _metadata_cache is None or force_reload:
        tom = get_tom_service()
        _metadata_cache = tom.extract_metadata()
        _metadata_cache["_original"] = copy.deepcopy(_metadata_cache)
    return _metadata_cache


def get_metadata() -> Optional[Dict[str, Any]]:
    return _metadata_cache


def clear_metadata():
    global _metadata_cache, _pending_changes
    _metadata_cache = None
    _pending_changes = []


def add_pending_change(change: Dict[str, Any]):
    _pending_changes.append({
        **change,
        "timestamp": datetime.utcnow().isoformat()
    })


def get_pending_changes() -> List[Dict[str, Any]]:
    return _pending_changes


def remove_pending_changes_for_table(table_id: str):
    """Remove alteracoes pendentes associadas a uma tabela."""
    global _pending_changes
    _pending_changes = [c for c in _pending_changes if c.get("tableId") != table_id]


def discard_pending_changes():
    global _pending_changes, _metadata_cache
    _pending_changes = []
    # Restaurar cache do original
    if _metadata_cache and "_original" in _metadata_cache:
        orig = copy.deepcopy(_metadata_cache["_original"])
        orig["_original"] = _metadata_cache["_original"]
        _metadata_cache = orig


def _recompute_stats():
    """Recalcula totais do cache para manter a UI consistente."""
    global _metadata_cache
    if not _metadata_cache:
        return

    tables = _metadata_cache.get("tables", [])
    _metadata_cache["totalTables"] = len(tables)
    _metadata_cache["totalColumns"] = sum(len(t.get("columns", [])) for t in tables)
    _metadata_cache["totalMeasures"] = sum(len(t.get("measures", [])) for t in tables)


def _sync_original_snapshot():
    """
    Atualiza o snapshot "_original" com o estado atual do cache sem recarregar do TOM.
    Isso evita uma nova extracao completa de metadados apos commit.
    """
    global _metadata_cache
    if not _metadata_cache:
        return

    current_state = copy.deepcopy({k: v for k, v in _metadata_cache.items() if k != "_original"})
    _metadata_cache["_original"] = current_state


def apply_change_to_cache(object_type: str, object_id: str, table_id: str, field: str, value: Any) -> bool:
    """Aplica mudanca ao cache local (sem salvar ainda)"""
    global _metadata_cache
    if not _metadata_cache:
        return False

    for table in _metadata_cache.get("tables", []):
        if table["id"] != table_id:
            continue

        if object_type == "table" and object_id == table_id:
            table[field] = value
            return True

        collection_map = {
            "column": "columns",
            "measure": "measures",
            "hierarchy": "hierarchies"
        }
        collection = collection_map.get(object_type)
        if collection:
            for obj in table.get(collection, []):
                if obj["id"] == object_id:
                    obj[field] = value
                    return True
    return False


def rename_table_in_cache(table_id: str, new_name: str) -> Optional[Dict[str, Any]]:
    """Renomeia tabela no cache e atualiza referencias visuais."""
    global _metadata_cache
    if not _metadata_cache:
        return None

    for table in _metadata_cache.get("tables", []):
        if table["id"] != table_id:
            continue

        old_name = table.get("name", table_id)
        table["name"] = new_name

        # Mantem IDs tecnicos, mas atualiza nomes exibidos.
        for obj in table.get("columns", []):
            obj["tableName"] = new_name
        for obj in table.get("measures", []):
            obj["tableName"] = new_name
        for obj in table.get("hierarchies", []):
            obj["tableName"] = new_name

        for rel in _metadata_cache.get("relationships", []):
            if rel.get("fromTable") == old_name:
                rel["fromTable"] = new_name
            if rel.get("toTable") == old_name:
                rel["toTable"] = new_name

        return {"oldName": old_name, "newName": new_name}

    return None


def set_table_hidden_in_cache(table_id: str, hidden: bool) -> Optional[Dict[str, Any]]:
    """Oculta/exibe tabela e todos os objetos internos no cache."""
    global _metadata_cache
    if not _metadata_cache:
        return None

    for table in _metadata_cache.get("tables", []):
        if table["id"] != table_id:
            continue

        affected_objects = 0

        table_old_hidden = table.get("hidden", False)
        table["hidden"] = hidden

        for object_type, collection in (
            ("column", "columns"),
            ("measure", "measures"),
            ("hierarchy", "hierarchies"),
        ):
            for obj in table.get(collection, []):
                old_hidden = obj.get("hidden", False)
                if old_hidden == hidden:
                    continue
                obj["hidden"] = hidden
                affected_objects += 1

        return {
            "tableId": table_id,
            "tableName": table.get("name", table_id),
            "tableOldHidden": table_old_hidden,
            "tableNewHidden": hidden,
            "affectedObjects": affected_objects,
        }

    return None


def delete_table_from_cache(table_id: str) -> Optional[Dict[str, Any]]:
    """Remove tabela e relacionamentos associados do cache."""
    global _metadata_cache
    if not _metadata_cache:
        return None

    tables = _metadata_cache.get("tables", [])
    table_idx = None
    table_obj = None
    for idx, table in enumerate(tables):
        if table.get("id") == table_id:
            table_idx = idx
            table_obj = table
            break

    if table_idx is None or table_obj is None:
        return None

    table_name = table_obj.get("name", table_id)
    removed_table = tables.pop(table_idx)

    relationships = _metadata_cache.get("relationships", [])
    remaining_relationships = []
    removed_relationships = []
    for rel in relationships:
        if rel.get("fromTable") == table_name or rel.get("toTable") == table_name:
            removed_relationships.append(rel)
        else:
            remaining_relationships.append(rel)
    _metadata_cache["relationships"] = remaining_relationships

    remove_pending_changes_for_table(table_id)
    _recompute_stats()

    return {
        "tableId": table_id,
        "tableName": table_name,
        "removedTable": removed_table,
        "removedRelationships": removed_relationships,
    }


def _build_effective_changes(changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Compacta a fila de pendencias para reduzir trabalho no commit:
    - Mantem apenas a ultima alteracao por (objeto + campo)
    - Se houver "__set_hidden_all__", remove alteracoes "hidden" anteriores da mesma tabela
    - Se houver "__delete__", remove alteracoes anteriores da mesma tabela
    """
    effective_map: "OrderedDict[tuple, Dict[str, Any]]" = OrderedDict()

    for change in changes:
        object_type = change.get("objectType")
        object_id = change.get("objectId")
        table_id = change.get("tableId")
        field = change.get("field")

        if not object_type or not table_id or not field:
            continue

        # Delete de tabela sobrescreve tudo que veio antes para a tabela.
        if object_type == "table" and field == "__delete__":
            keys_to_remove = [k for k, c in effective_map.items() if c.get("tableId") == table_id]
            for k in keys_to_remove:
                effective_map.pop(k, None)

            delete_key = (object_type, object_id, table_id, field)
            effective_map[delete_key] = change
            continue

        # Se existir delete anterior e chegou nova acao para a mesma tabela,
        # considera a ultima acao como verdade (remove o delete antigo).
        delete_keys = [
            k for k, c in effective_map.items()
            if c.get("tableId") == table_id and c.get("objectType") == "table" and c.get("field") == "__delete__"
        ]
        for k in delete_keys:
            effective_map.pop(k, None)

        # Ocultar/exibir tabela inteira torna pendencias "hidden" anteriores redundantes.
        if object_type == "table" and field == "__set_hidden_all__":
            keys_to_remove = [
                k for k, c in effective_map.items()
                if c.get("tableId") == table_id and (
                    c.get("field") == "hidden"
                    or (c.get("objectType") == "table" and c.get("field") == "__set_hidden_all__")
                )
            ]
            for k in keys_to_remove:
                effective_map.pop(k, None)

        key = (object_type, object_id, table_id, field)
        if key in effective_map:
            # Move para o fim para refletir a ultima acao.
            effective_map.pop(key, None)
        effective_map[key] = change

    return list(effective_map.values())


def commit_pending_changes() -> Dict[str, Any]:
    """Aplica todas as mudancas pendentes ao servidor"""
    global _pending_changes
    tom = get_tom_service()
    started_at = datetime.utcnow()

    if not _pending_changes:
        return {
            "success": 0,
            "failed": 0,
            "errors": [],
            "appliedAt": datetime.utcnow().isoformat(),
            "durationMs": 0,
            "metadataReloaded": False,
            "requestedChanges": 0,
            "effectiveChanges": 0
        }

    requested_count = len(_pending_changes)
    effective_changes = _build_effective_changes(_pending_changes)
    results = {"success": 0, "failed": 0, "errors": []}

    # Caminho preferencial: aplica tudo em lote com um unico SaveChanges()
    try:
        if hasattr(tom, "apply_updates_batch"):
            batch_result = tom.apply_updates_batch(effective_changes)
            results["success"] = batch_result.get("success", 0)
            results["failed"] = batch_result.get("failed", 0)
            results["errors"] = batch_result.get("errors", [])
        else:
            raise AttributeError("TOMService sem apply_updates_batch")
    except Exception as batch_error:
        # Fallback de compatibilidade: aplica uma-a-uma
        results["errors"].append(f"Falha no modo lote ({str(batch_error)}). Aplicando em modo legado.")
        results["success"] = 0
        results["failed"] = 0

        for change in effective_changes:
            try:
                tom.apply_update(
                    object_type=change["objectType"],
                    object_id=change["objectId"],
                    table_id=change["tableId"],
                    field=change["field"],
                    value=change["value"]
                )
                results["success"] += 1
            except Exception as e:
                results["failed"] += 1
                obj_id = change.get("objectId", change.get("tableId", "<desconhecido>"))
                field = change.get("field", "<campo>")
                results["errors"].append(f"Erro em {obj_id}.{field}: {str(e)}")

    if results["failed"] == 0:
        _pending_changes = []
        # Em vez de recarregar o modelo inteiro (lento), marca estado atual como baseline.
        _sync_original_snapshot()

    finished_at = datetime.utcnow()
    results["appliedAt"] = finished_at.isoformat()
    results["durationMs"] = int((finished_at - started_at).total_seconds() * 1000)
    results["metadataReloaded"] = False
    results["requestedChanges"] = requested_count
    results["effectiveChanges"] = len(effective_changes)
    return results


def export_metadata_backup() -> Dict[str, Any]:
    """Exporta copia dos metadados para backup antes de gravar"""
    meta = get_metadata()
    if not meta:
        return {}
    export = copy.deepcopy(meta)
    export.pop("_original", None)
    export["exportedAt"] = datetime.utcnow().isoformat()
    export["exportType"] = "pre_save_backup"
    return export
