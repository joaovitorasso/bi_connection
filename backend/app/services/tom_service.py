import os
import glob
import json
import subprocess
from typing import Optional, List, Dict, Any
from pathlib import Path
import re
import sys


class TOMService:
    """
    Servico de integracao com Tabular Object Model (TOM).

    Estrategias de conexao (em ordem de tentativa):
    1. pythonnet + Microsoft.AnalysisServices.Tabular (se disponivel)
    2. XMLA/ADOMD via pythonnet com Microsoft.AnalysisServices
    3. Conexao XMLA via HTTP (para endpoint remoto)
    4. Modo demonstracao com dados mock (para desenvolvimento/teste)

    Para Power BI Desktop local:
    - Detecta porta do AS local via arquivo msmdsrv.port.txt em:
      %LocalAppData%\\Microsoft\\Power BI Desktop\\AnalysisServicesWorkspaces\\
    - Conecta via localhost:<porta>

    Para Power BI Service (XMLA remote):
    - Usa endpoint: powerbi://api.powerbi.com/v1.0/myorg/<workspace>
    - Requer credenciais Azure AD
    """

    def __init__(self):
        self._connection = None
        self._server = None
        self._database = None
        self._mode = None
        self._use_pythonnet = False
        self._demo_mode = False
        self._pythonnet_init_error = ""
        self._try_init_pythonnet()

    def _try_init_pythonnet(self):
        """Tenta inicializar pythonnet para integracao com .NET TOM"""
        try:
            import clr
            import sys

            # Tenta localizar DLLs do TOM em caminhos comuns
            candidate_dlls: List[Path] = []

            env_dll = os.environ.get("TOM_ASSEMBLY_PATH", "").strip()
            if env_dll:
                env_path = Path(env_dll)
                if env_path.exists():
                    candidate_dlls.append(env_path)

            known_dll_paths = [
                r"C:\Program Files\Microsoft.NET\ADOMD.NET\160\Microsoft.AnalysisServices.Tabular.dll",
                r"C:\Program Files\Microsoft SQL Server\160\SDK\Assemblies\Microsoft.AnalysisServices.Tabular.dll",
                r"C:\Program Files\Microsoft SQL Server Management Studio 21\Release\Common7\IDE\Microsoft.AnalysisServices.Tabular.dll",
                r"C:\Program Files\Tabular Editor 3\Microsoft.AnalysisServices.Tabular.dll",
                r"C:\Program Files\Power BI ALM Toolkit\Power BI ALM Toolkit\Microsoft.AnalysisServices.Tabular.dll",
                r"C:\Program Files\On-premises data gateway\FabricIntegrationRuntime\5.0\Gateway\Microsoft.AnalysisServices.Tabular.dll",
            ]
            for raw_path in known_dll_paths:
                dll_path = Path(raw_path)
                if dll_path.exists():
                    candidate_dlls.append(dll_path)

            # Tenta localizar via NuGet local
            nuget_path = Path.home() / ".nuget" / "packages"
            if nuget_path.exists():
                candidate_dlls.extend(nuget_path.glob("**/Microsoft.AnalysisServices.Tabular.dll"))

            # Adiciona diretorios ao sys.path para resolucao de dependencias
            added_dirs = set()
            for dll_path in candidate_dlls:
                dll_dir = str(dll_path.parent)
                if dll_dir not in added_dirs:
                    sys.path.append(dll_dir)
                    added_dirs.add(dll_dir)

            # 1) Tenta por nome no contexto atual
            # 2) Se falhar, tenta por caminho completo
            try:
                clr.AddReference("Microsoft.AnalysisServices.Tabular")
            except Exception:
                loaded = False
                for dll_path in candidate_dlls:
                    try:
                        clr.AddReference(str(dll_path))
                        loaded = True
                        break
                    except Exception:
                        continue
                if not loaded:
                    raise

            from Microsoft.AnalysisServices.Tabular import Server as TabularServer  # noqa: F401
            self._use_pythonnet = True
            self._pythonnet_init_error = ""
        except Exception as e:
            self._use_pythonnet = False
            self._pythonnet_init_error = str(e)

    def find_local_pbi_port(self) -> Optional[int]:
        """
        Encontra a porta do Analysis Services local do Power BI Desktop.
        O PBI Desktop cria workspaces em:
        %LocalAppData%\\Microsoft\\Power BI Desktop\\AnalysisServicesWorkspaces\\
        Cada workspace tem Data\\msmdsrv.port.txt com o numero da porta.
        """
        port_files: List[Path] = []

        # Padrrao instalador MSI
        local_appdata = Path(os.environ.get("LOCALAPPDATA", ""))
        base_candidates = [
            local_appdata / "Microsoft" / "Power BI Desktop" / "AnalysisServicesWorkspaces",
            local_appdata / "Microsoft" / "Power BI Desktop Store App" / "AnalysisServicesWorkspaces",
        ]

        # Tentativas para instalacao via Store (Microsoft.MicrosoftPowerBIDesktop_*)
        packages_root = local_appdata / "Packages"
        if packages_root.exists():
            for pkg_dir in packages_root.glob("Microsoft.MicrosoftPowerBIDesktop*"):
                base_candidates.extend(
                    [
                        pkg_dir / "LocalCache" / "Microsoft" / "Power BI Desktop" / "AnalysisServicesWorkspaces",
                        pkg_dir / "LocalCache" / "Local" / "Microsoft" / "Power BI Desktop" / "AnalysisServicesWorkspaces",
                        pkg_dir / "LocalState" / "Microsoft" / "Power BI Desktop" / "AnalysisServicesWorkspaces",
                    ]
                )

        for workspace_base in base_candidates:
            if not workspace_base.exists():
                continue
            try:
                port_files.extend(workspace_base.glob("*/Data/msmdsrv.port.txt"))
                port_files.extend(workspace_base.glob("*/msmdsrv.port.txt"))
            except Exception:
                continue

        # Fallback: procura recursiva em pasta de pacote (Store) quando necessario
        if not port_files and packages_root.exists():
            try:
                for pkg_dir in packages_root.glob("Microsoft.MicrosoftPowerBIDesktop*"):
                    port_files.extend(pkg_dir.rglob("msmdsrv.port.txt"))
            except Exception:
                pass

        if not port_files:
            return None

        # Pega o arquivo mais recente com porta valida
        def _mtime(path: Path) -> float:
            try:
                return path.stat().st_mtime
            except Exception:
                return 0.0

        port_files.sort(key=_mtime, reverse=True)

        for port_file in port_files:
            try:
                port_text = port_file.read_text().strip()
                port = int(port_text)
                if 1 <= port <= 65535:
                    return port
            except Exception:
                continue

        return None

    def connect_local(self) -> Dict[str, Any]:
        """Conecta ao modelo aberto no Power BI Desktop"""
        port = self.find_local_pbi_port()
        if port is None:
            # Tentar encontrar via netstat
            port = self._find_port_via_netstat()

        if port is None:
            # Modo demonstracao para desenvolvimento
            self._demo_mode = True
            self._mode = "local_demo"
            desktop_running = self._is_process_running("PBIDesktop") or self._is_process_running("msmdsrv")
            message = (
                "Power BI Desktop detectado, mas nao foi possivel identificar a porta local. Usando modo demonstracao."
                if desktop_running
                else "Power BI Desktop nao encontrado. Usando modo demonstracao."
            )
            return {
                "connected": True,
                "demo": True,
                "message": message
            }

        server_url = f"localhost:{port}"
        return self._connect_to_server(server_url, mode="local")

    def _find_port_via_netstat(self) -> Optional[int]:
        """Tenta encontrar porta via processos msmdsrv.exe"""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-Process msmdsrv -ErrorAction SilentlyContinue | Select-Object Id | ConvertTo-Json"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0 or not result.stdout.strip():
                return None

            pid_list = self._parse_msmdsrv_ids(result.stdout)
            if not pid_list:
                return None

            # Encontrar porta via netstat associada ao processo
            netstat_result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True, timeout=5
            )

            candidate_ports: List[int] = []
            for line in netstat_result.stdout.splitlines():
                parts = line.split()
                # Exemplo: TCP 127.0.0.1:59341 0.0.0.0:0 LISTENING 40304
                if len(parts) < 5:
                    continue
                proto, local_ep, _, state, pid = parts[:5]
                if proto.upper() != "TCP" or state.upper() != "LISTENING":
                    continue
                if pid not in pid_list:
                    continue

                port_match = re.search(r":(\d+)$", local_ep)
                if not port_match:
                    continue

                port = int(port_match.group(1))
                if 49152 <= port <= 65535:
                    candidate_ports.append(port)

            for port in sorted(set(candidate_ports), reverse=True):
                if self._use_pythonnet:
                    # Quando TOM esta disponivel, valida para reduzir falso-positivo
                    if self._test_as_connection(f"localhost:{port}"):
                        return port
                else:
                    # Sem TOM, retorna mesmo assim para evitar falso "desktop nao encontrado"
                    return port
        except Exception:
            pass
        return None

    def _parse_msmdsrv_ids(self, payload: str) -> List[str]:
        """Converte saida JSON do PowerShell em lista de PIDs (string)."""
        try:
            data = json.loads(payload)
        except Exception:
            return []

        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            return []

        ids: List[str] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            process_id = item.get("Id")
            if process_id is not None:
                ids.append(str(process_id))
        return ids

    def _is_process_running(self, process_name: str) -> bool:
        """Verifica se um processo esta em execucao."""
        try:
            result = subprocess.run(
                ["powershell", "-Command", f"Get-Process {process_name} -ErrorAction SilentlyContinue | Select-Object -First 1"],
                capture_output=True, text=True, timeout=5
            )
            return bool(result.stdout.strip())
        except Exception:
            return False

    def _test_as_connection(self, server_url: str) -> bool:
        """Testa se um endereco e um servidor AS valido"""
        try:
            if self._use_pythonnet:
                import clr
                from Microsoft.AnalysisServices.Tabular import Server
                s = Server()
                s.Connect(f"Data Source={server_url}")
                s.Disconnect()
                return True
        except Exception:
            pass
        return False

    def connect_remote(self, workspace: str, model: str, username: str = None, password: str = None) -> Dict[str, Any]:
        """Conecta ao modelo no Power BI Service via XMLA"""
        server_url = f"powerbi://api.powerbi.com/v1.0/myorg/{workspace}"
        conn_str = f"Data Source={server_url};Initial Catalog={model}"
        if username and password:
            conn_str += f";User ID={username};Password={password}"

        return self._connect_to_server(server_url, database=model, mode="remote", conn_str=conn_str)

    def _connect_to_server(self, server_url: str, database: str = None, mode: str = "local", conn_str: str = None) -> Dict[str, Any]:
        """Conecta ao servidor AS"""
        if self._use_pythonnet:
            try:
                from Microsoft.AnalysisServices.Tabular import Server
                server = Server()
                cs = conn_str or f"Data Source={server_url}"
                server.Connect(cs)
                self._server = server

                if database:
                    self._database = server.Databases[database]
                elif server.Databases.Count > 0:
                    self._database = server.Databases[0]

                self._mode = mode
                db_name = self._database.Name if self._database else "N/A"
                return {
                    "connected": True,
                    "serverUrl": server_url,
                    "databaseName": db_name,
                    "modelName": db_name,
                    "demo": False
                }
            except Exception as e:
                # Fallback para modo demo
                self._demo_mode = True
                self._mode = mode
                return {
                    "connected": True,
                    "demo": True,
                    "serverUrl": server_url,
                    "message": f"Nao foi possivel conectar via TOM: {str(e)}. Usando modo demonstracao.",
                    "error": str(e)
                }
        else:
            # Sem pythonnet, usar modo demo
            self._demo_mode = True
            self._mode = mode
            message = "pythonnet/AMO nao disponivel para conexao TOM. Instale dependencias TOM e reinicie. Usando modo demonstracao."
            if "No module named 'clr'" in self._pythonnet_init_error:
                py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
                message += f" Dica: para Python {py_version}, use pythonnet==3.0.5."
            if self._pythonnet_init_error:
                error_hint = self._pythonnet_init_error.replace("\n", " ").strip()
                message = f"{message} Detalhe: {error_hint}"
            return {
                "connected": True,
                "demo": True,
                "serverUrl": server_url,
                "message": message
            }

    def get_databases(self) -> List[str]:
        """Lista databases disponiveis no servidor"""
        if self._demo_mode or not self._server:
            return ["ContosoRetail_Demo", "FinancialModel_Demo", "SalesAnalysis_Demo"]

        try:
            return [db.Name for db in self._server.Databases]
        except Exception:
            return []

    def extract_metadata(self) -> Dict[str, Any]:
        """Extrai todos os metadados do modelo"""
        if self._demo_mode:
            return self._get_demo_metadata()

        if not self._database:
            raise Exception("Nao conectado a nenhum banco de dados")

        return self._extract_from_tom()

    def _is_technical_table_name(self, table_name: str) -> bool:
        """
        Filtra tabelas tecnicas do Auto Date/Time, que nao devem aparecer na UI.
        """
        if not table_name:
            return False

        normalized = table_name.strip().lower()
        return (
            normalized.startswith("localdatetable_")
            or normalized.startswith("datetabletemplate_")
        )

    def _extract_from_tom(self) -> Dict[str, Any]:
        """Extrai metadados via TOM (pythonnet)"""
        try:
            model = self._database.Model
            tables_data = []
            relationships_data = []
            included_table_names = set()

            for table in model.Tables:
                if self._is_technical_table_name(table.Name):
                    continue

                table_data = {
                    "id": table.Name,
                    "name": table.Name,
                    "description": table.Description or "",
                    "hidden": table.IsHidden,
                    "isDateTable": False,
                    "columns": [],
                    "measures": [],
                    "hierarchies": []
                }

                # Colunas
                for col in table.Columns:
                    if col.Type.ToString() == "RowNumber":
                        continue
                    col_data = {
                        "id": f"{table.Name}.{col.Name}",
                        "tableId": table.Name,
                        "tableName": table.Name,
                        "name": col.Name,
                        "description": col.Description or "",
                        "hidden": col.IsHidden,
                        "dataType": col.DataType.ToString(),
                        "formatString": col.FormatString or "",
                        "displayFolder": col.DisplayFolder or "",
                        "sortByColumn": col.SortByColumn.Name if col.SortByColumn else "",
                        "summarizeBy": col.SummarizeBy.ToString() if hasattr(col, 'SummarizeBy') else "Default",
                        "expression": col.Expression if hasattr(col, 'Expression') else ""
                    }
                    table_data["columns"].append(col_data)

                # Medidas
                for measure in table.Measures:
                    meas_data = {
                        "id": f"{table.Name}.{measure.Name}",
                        "tableId": table.Name,
                        "tableName": table.Name,
                        "name": measure.Name,
                        "description": measure.Description or "",
                        "hidden": measure.IsHidden,
                        "formatString": measure.FormatString or "",
                        "displayFolder": measure.DisplayFolder or "",
                        "expression": measure.Expression or ""
                    }
                    table_data["measures"].append(meas_data)

                # Hierarquias
                for hier in table.Hierarchies:
                    hier_data = {
                        "id": f"{table.Name}.{hier.Name}",
                        "tableId": table.Name,
                        "tableName": table.Name,
                        "name": hier.Name,
                        "description": hier.Description or "",
                        "hidden": hier.IsHidden,
                        "displayFolder": hier.DisplayFolder or "",
                        "levels": [lvl.Name for lvl in hier.Levels]
                    }
                    table_data["hierarchies"].append(hier_data)

                tables_data.append(table_data)
                included_table_names.add(table.Name)

            # Relacionamentos
            for rel in model.Relationships:
                from_table_name = rel.FromTable.Name
                to_table_name = rel.ToTable.Name

                # Mantem apenas relacionamentos entre tabelas exibidas
                if from_table_name not in included_table_names or to_table_name not in included_table_names:
                    continue

                rel_data = {
                    "id": str(rel.Name),
                    "fromTable": from_table_name,
                    "fromColumn": rel.FromColumn.Name,
                    "toTable": to_table_name,
                    "toColumn": rel.ToColumn.Name,
                    "cardinality": rel.FromCardinality.ToString() + "_" + rel.ToCardinality.ToString(),
                    "crossFilteringBehavior": rel.CrossFilteringBehavior.ToString(),
                    "active": rel.IsActive
                }
                relationships_data.append(rel_data)

            from datetime import datetime
            total_cols = sum(len(t["columns"]) for t in tables_data)
            total_meas = sum(len(t["measures"]) for t in tables_data)

            return {
                "modelName": self._database.Name,
                "databaseName": self._database.Name,
                "connectionString": "",
                "tables": tables_data,
                "relationships": relationships_data,
                "extractedAt": datetime.utcnow().isoformat(),
                "totalTables": len(tables_data),
                "totalColumns": total_cols,
                "totalMeasures": total_meas,
                "demo": False
            }
        except Exception as e:
            raise Exception(f"Erro ao extrair metadados via TOM: {str(e)}")

    def _apply_change_without_save(self, model: Any, change: Dict[str, Any]) -> None:
        """
        Aplica uma mudanca no modelo em memoria sem chamar SaveChanges().
        """
        object_type = change["objectType"]
        object_id = change["objectId"]
        table_id = change["tableId"]
        field = change["field"]
        value = change.get("value")

        table = model.Tables[table_id]

        # Excluir tabela inteira
        if object_type == "table" and field == "__delete__":
            model.Tables.Remove(table)
            return

        # Ocultar/exibir tabela inteira + objetos internos
        if object_type == "table" and field == "__set_hidden_all__":
            hidden_value = bool(value)
            table.IsHidden = hidden_value

            for col in table.Columns:
                if hasattr(col, "Type") and col.Type.ToString() == "RowNumber":
                    continue
                col.IsHidden = hidden_value
            for measure in table.Measures:
                measure.IsHidden = hidden_value
            for hier in table.Hierarchies:
                hier.IsHidden = hidden_value
            return

        if object_type == "column":
            col_name = object_id.split(".", 1)[1] if "." in object_id else object_id
            obj = table.Columns[col_name]
        elif object_type == "measure":
            meas_name = object_id.split(".", 1)[1] if "." in object_id else object_id
            obj = table.Measures[meas_name]
        elif object_type == "table":
            obj = table
        elif object_type == "hierarchy":
            hier_name = object_id.split(".", 1)[1] if "." in object_id else object_id
            obj = table.Hierarchies[hier_name]
        else:
            raise Exception(f"Tipo de objeto desconhecido: {object_type}")

        field_map = {
            "description": "Description",
            "hidden": "IsHidden",
            "formatString": "FormatString",
            "displayFolder": "DisplayFolder",
            "name": "Name",
            "expression": "Expression",
        }

        dotnet_field = field_map.get(field, field)
        setattr(obj, dotnet_field, value)

    def apply_updates_batch(self, changes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aplica uma lista de mudancas com um unico SaveChanges(), para melhorar performance.
        """
        if self._demo_mode:
            return {"success": len(changes), "failed": 0, "errors": []}

        if not self._database:
            raise Exception("Nao conectado")

        model = self._database.Model
        results = {"success": 0, "failed": 0, "errors": []}

        # Processa deletes por ultimo para evitar remover tabela antes de outras alteracoes nela.
        normal_changes = [c for c in changes if c.get("field") != "__delete__"]
        delete_changes = [c for c in changes if c.get("field") == "__delete__"]
        ordered_changes = normal_changes + delete_changes

        for change in ordered_changes:
            try:
                self._apply_change_without_save(model, change)
                results["success"] += 1
            except Exception as e:
                results["failed"] += 1
                obj_id = change.get("objectId", change.get("tableId", "<desconhecido>"))
                field = change.get("field", "<campo>")
                results["errors"].append(f"Erro em {obj_id}.{field}: {str(e)}")

        if results["success"] > 0:
            try:
                model.SaveChanges()
            except Exception as e:
                # Se SaveChanges falhar, considera todas as alteracoes em memoria como falhas.
                results["errors"].append(f"Erro ao salvar em lote: {str(e)}")
                results["failed"] += results["success"]
                results["success"] = 0

        return results

    def apply_update(self, object_type: str, object_id: str, table_id: str, field: str, value: Any) -> bool:
        """Aplica uma atualizacao a um objeto do modelo"""
        if self._demo_mode:
            return True  # Simula sucesso no modo demo

        if not self._database:
            raise Exception("Nao conectado")

        try:
            model = self._database.Model
            self._apply_change_without_save(model, {
                "objectType": object_type,
                "objectId": object_id,
                "tableId": table_id,
                "field": field,
                "value": value,
            })
            model.SaveChanges()
            return True
        except Exception as e:
            raise Exception(f"Erro ao aplicar atualizacao: {str(e)}")

    def disconnect(self):
        """Desconecta do servidor"""
        try:
            if self._server and self._use_pythonnet:
                self._server.Disconnect()
        except Exception:
            pass
        self._server = None
        self._database = None
        self._demo_mode = False

    def _get_demo_metadata(self) -> Dict[str, Any]:
        """Retorna metadados de demonstracao para desenvolvimento/teste"""
        from datetime import datetime

        tables = [
            {
                "id": "fSales",
                "name": "fSales",
                "description": "Tabela fato de vendas",
                "hidden": False,
                "isDateTable": False,
                "columns": [
                    {"id": "fSales.SalesKey", "tableId": "fSales", "tableName": "fSales", "name": "SalesKey", "description": "Chave da venda", "hidden": False, "dataType": "Int64", "formatString": "", "displayFolder": "", "sortByColumn": "", "summarizeBy": "None", "expression": ""},
                    {"id": "fSales.OrderDate", "tableId": "fSales", "tableName": "fSales", "name": "OrderDate", "description": "Data do pedido", "hidden": False, "dataType": "DateTime", "formatString": "dd/MM/yyyy", "displayFolder": "Datas", "sortByColumn": "", "summarizeBy": "None", "expression": ""},
                    {"id": "fSales.CustomerKey", "tableId": "fSales", "tableName": "fSales", "name": "CustomerKey", "description": "Chave do cliente", "hidden": True, "dataType": "Int64", "formatString": "", "displayFolder": "Chaves", "sortByColumn": "", "summarizeBy": "None", "expression": ""},
                    {"id": "fSales.ProductKey", "tableId": "fSales", "tableName": "fSales", "name": "ProductKey", "description": "Chave do produto", "hidden": True, "dataType": "Int64", "formatString": "", "displayFolder": "Chaves", "sortByColumn": "", "summarizeBy": "None", "expression": ""},
                    {"id": "fSales.Quantity", "tableId": "fSales", "tableName": "fSales", "name": "Quantity", "description": "Quantidade vendida", "hidden": False, "dataType": "Int64", "formatString": "#,0", "displayFolder": "Metricas", "sortByColumn": "", "summarizeBy": "Sum", "expression": ""},
                    {"id": "fSales.UnitPrice", "tableId": "fSales", "tableName": "fSales", "name": "UnitPrice", "description": "Preco unitario", "hidden": False, "dataType": "Decimal", "formatString": "R$ #,0.00", "displayFolder": "Metricas", "sortByColumn": "", "summarizeBy": "Sum", "expression": ""},
                    {"id": "fSales.SalesAmount", "tableId": "fSales", "tableName": "fSales", "name": "SalesAmount", "description": "Valor total da venda", "hidden": False, "dataType": "Decimal", "formatString": "R$ #,0.00", "displayFolder": "Metricas", "sortByColumn": "", "summarizeBy": "Sum", "expression": ""},
                    {"id": "fSales.Discount", "tableId": "fSales", "tableName": "fSales", "name": "Discount", "description": "Desconto aplicado", "hidden": False, "dataType": "Decimal", "formatString": "0.00%", "displayFolder": "Metricas", "sortByColumn": "", "summarizeBy": "Average", "expression": ""},
                ],
                "measures": [
                    {"id": "fSales.Total Vendas", "tableId": "fSales", "tableName": "fSales", "name": "Total Vendas", "description": "Soma do valor total de vendas", "hidden": False, "formatString": "R$ #,0.00", "displayFolder": "KPIs", "expression": "SUM(fSales[SalesAmount])"},
                    {"id": "fSales.Qtd Pedidos", "tableId": "fSales", "tableName": "fSales", "name": "Qtd Pedidos", "description": "Contagem de pedidos unicos", "hidden": False, "formatString": "#,0", "displayFolder": "KPIs", "expression": "DISTINCTCOUNT(fSales[SalesKey])"},
                    {"id": "fSales.Ticket Medio", "tableId": "fSales", "tableName": "fSales", "name": "Ticket Medio", "description": "Valor medio por pedido", "hidden": False, "formatString": "R$ #,0.00", "displayFolder": "KPIs", "expression": "DIVIDE([Total Vendas], [Qtd Pedidos], 0)"},
                    {"id": "fSales.Qtd Produtos Vendidos", "tableId": "fSales", "tableName": "fSales", "name": "Qtd Produtos Vendidos", "description": "Soma das quantidades vendidas", "hidden": False, "formatString": "#,0", "displayFolder": "KPIs", "expression": "SUM(fSales[Quantity])"},
                    {"id": "fSales.Vendas YTD", "tableId": "fSales", "tableName": "fSales", "name": "Vendas YTD", "description": "Vendas acumuladas no ano", "hidden": False, "formatString": "R$ #,0.00", "displayFolder": "Time Intelligence", "expression": "TOTALYTD([Total Vendas], dCalendario[Date])"},
                    {"id": "fSales.Vendas LY", "tableId": "fSales", "tableName": "fSales", "name": "Vendas LY", "description": "Vendas do ano anterior", "hidden": False, "formatString": "R$ #,0.00", "displayFolder": "Time Intelligence", "expression": "CALCULATE([Total Vendas], SAMEPERIODLASTYEAR(dCalendario[Date]))"},
                    {"id": "fSales.Crescimento YoY", "tableId": "fSales", "tableName": "fSales", "name": "Crescimento YoY", "description": "Crescimento ano a ano", "hidden": False, "formatString": "0.0%", "displayFolder": "Time Intelligence", "expression": "DIVIDE([Total Vendas] - [Vendas LY], [Vendas LY], BLANK())"},
                ],
                "hierarchies": []
            },
            {
                "id": "dCliente",
                "name": "dCliente",
                "description": "Dimensao de clientes",
                "hidden": False,
                "isDateTable": False,
                "columns": [
                    {"id": "dCliente.CustomerKey", "tableId": "dCliente", "tableName": "dCliente", "name": "CustomerKey", "description": "Chave do cliente", "hidden": True, "dataType": "Int64", "formatString": "", "displayFolder": "Chaves", "sortByColumn": "", "summarizeBy": "None", "expression": ""},
                    {"id": "dCliente.CustomerName", "tableId": "dCliente", "tableName": "dCliente", "name": "CustomerName", "description": "Nome completo do cliente", "hidden": False, "dataType": "String", "formatString": "", "displayFolder": "Identificacao", "sortByColumn": "", "summarizeBy": "None", "expression": ""},
                    {"id": "dCliente.Email", "tableId": "dCliente", "tableName": "dCliente", "name": "Email", "description": "E-mail do cliente", "hidden": False, "dataType": "String", "formatString": "", "displayFolder": "Identificacao", "sortByColumn": "", "summarizeBy": "None", "expression": ""},
                    {"id": "dCliente.City", "tableId": "dCliente", "tableName": "dCliente", "name": "City", "description": "Cidade", "hidden": False, "dataType": "String", "formatString": "", "displayFolder": "Localizacao", "sortByColumn": "", "summarizeBy": "None", "expression": ""},
                    {"id": "dCliente.State", "tableId": "dCliente", "tableName": "dCliente", "name": "State", "description": "Estado", "hidden": False, "dataType": "String", "formatString": "", "displayFolder": "Localizacao", "sortByColumn": "", "summarizeBy": "None", "expression": ""},
                    {"id": "dCliente.Country", "tableId": "dCliente", "tableName": "dCliente", "name": "Country", "description": "Pais", "hidden": False, "dataType": "String", "formatString": "", "displayFolder": "Localizacao", "sortByColumn": "", "summarizeBy": "None", "expression": ""},
                    {"id": "dCliente.Segment", "tableId": "dCliente", "tableName": "dCliente", "name": "Segment", "description": "Segmento do cliente", "hidden": False, "dataType": "String", "formatString": "", "displayFolder": "Segmentacao", "sortByColumn": "", "summarizeBy": "None", "expression": ""},
                ],
                "measures": [
                    {"id": "dCliente.Total Clientes", "tableId": "dCliente", "tableName": "dCliente", "name": "Total Clientes", "description": "Contagem de clientes unicos", "hidden": False, "formatString": "#,0", "displayFolder": "", "expression": "DISTINCTCOUNT(dCliente[CustomerKey])"},
                ],
                "hierarchies": [
                    {"id": "dCliente.Geo Hierarchy", "tableId": "dCliente", "tableName": "dCliente", "name": "Geo Hierarchy", "description": "Hierarquia geografica", "hidden": False, "displayFolder": "Localizacao", "levels": ["Country", "State", "City"]}
                ]
            },
            {
                "id": "dProduto",
                "name": "dProduto",
                "description": "Dimensao de produtos",
                "hidden": False,
                "isDateTable": False,
                "columns": [
                    {"id": "dProduto.ProductKey", "tableId": "dProduto", "tableName": "dProduto", "name": "ProductKey", "description": "Chave do produto", "hidden": True, "dataType": "Int64", "formatString": "", "displayFolder": "Chaves", "sortByColumn": "", "summarizeBy": "None", "expression": ""},
                    {"id": "dProduto.ProductName", "tableId": "dProduto", "tableName": "dProduto", "name": "ProductName", "description": "Nome do produto", "hidden": False, "dataType": "String", "formatString": "", "displayFolder": "Identificacao", "sortByColumn": "", "summarizeBy": "None", "expression": ""},
                    {"id": "dProduto.Category", "tableId": "dProduto", "tableName": "dProduto", "name": "Category", "description": "Categoria do produto", "hidden": False, "dataType": "String", "formatString": "", "displayFolder": "Classificacao", "sortByColumn": "", "summarizeBy": "None", "expression": ""},
                    {"id": "dProduto.Subcategory", "tableId": "dProduto", "tableName": "dProduto", "name": "Subcategory", "description": "Subcategoria do produto", "hidden": False, "dataType": "String", "formatString": "", "displayFolder": "Classificacao", "sortByColumn": "", "summarizeBy": "None", "expression": ""},
                    {"id": "dProduto.Brand", "tableId": "dProduto", "tableName": "dProduto", "name": "Brand", "description": "Marca do produto", "hidden": False, "dataType": "String", "formatString": "", "displayFolder": "Classificacao", "sortByColumn": "", "summarizeBy": "None", "expression": ""},
                    {"id": "dProduto.UnitCost", "tableId": "dProduto", "tableName": "dProduto", "name": "UnitCost", "description": "Custo unitario", "hidden": False, "dataType": "Decimal", "formatString": "R$ #,0.00", "displayFolder": "Financas", "sortByColumn": "", "summarizeBy": "Average", "expression": ""},
                    {"id": "dProduto.ListPrice", "tableId": "dProduto", "tableName": "dProduto", "name": "ListPrice", "description": "Preco de lista", "hidden": False, "dataType": "Decimal", "formatString": "R$ #,0.00", "displayFolder": "Financas", "sortByColumn": "", "summarizeBy": "Average", "expression": ""},
                ],
                "measures": [],
                "hierarchies": [
                    {"id": "dProduto.Product Hierarchy", "tableId": "dProduto", "tableName": "dProduto", "name": "Product Hierarchy", "description": "Hierarquia de categorias de produto", "hidden": False, "displayFolder": "Classificacao", "levels": ["Category", "Subcategory", "Brand", "ProductName"]}
                ]
            },
            {
                "id": "dCalendario",
                "name": "dCalendario",
                "description": "Tabela de calendario (Date Table)",
                "hidden": False,
                "isDateTable": True,
                "columns": [
                    {"id": "dCalendario.Date", "tableId": "dCalendario", "tableName": "dCalendario", "name": "Date", "description": "Data completa", "hidden": False, "dataType": "DateTime", "formatString": "dd/MM/yyyy", "displayFolder": "", "sortByColumn": "", "summarizeBy": "None", "expression": ""},
                    {"id": "dCalendario.Year", "tableId": "dCalendario", "tableName": "dCalendario", "name": "Year", "description": "Ano", "hidden": False, "dataType": "Int64", "formatString": "0", "displayFolder": "Calendario", "sortByColumn": "", "summarizeBy": "None", "expression": ""},
                    {"id": "dCalendario.YearMonth", "tableId": "dCalendario", "tableName": "dCalendario", "name": "YearMonth", "description": "Ano e mes (YYYYMM)", "hidden": True, "dataType": "Int64", "formatString": "0", "displayFolder": "Calendario", "sortByColumn": "", "summarizeBy": "None", "expression": ""},
                    {"id": "dCalendario.MonthName", "tableId": "dCalendario", "tableName": "dCalendario", "name": "MonthName", "description": "Nome do mes", "hidden": False, "dataType": "String", "formatString": "", "displayFolder": "Calendario", "sortByColumn": "YearMonth", "summarizeBy": "None", "expression": ""},
                    {"id": "dCalendario.Quarter", "tableId": "dCalendario", "tableName": "dCalendario", "name": "Quarter", "description": "Trimestre", "hidden": False, "dataType": "String", "formatString": "", "displayFolder": "Calendario", "sortByColumn": "", "summarizeBy": "None", "expression": ""},
                    {"id": "dCalendario.WeekDay", "tableId": "dCalendario", "tableName": "dCalendario", "name": "WeekDay", "description": "Dia da semana", "hidden": False, "dataType": "String", "formatString": "", "displayFolder": "Calendario", "sortByColumn": "", "summarizeBy": "None", "expression": ""},
                    {"id": "dCalendario.IsWeekend", "tableId": "dCalendario", "tableName": "dCalendario", "name": "IsWeekend", "description": "Indica fim de semana", "hidden": True, "dataType": "Boolean", "formatString": "", "displayFolder": "Calendario", "sortByColumn": "", "summarizeBy": "None", "expression": ""},
                ],
                "measures": [],
                "hierarchies": [
                    {"id": "dCalendario.Date Hierarchy", "tableId": "dCalendario", "tableName": "dCalendario", "name": "Date Hierarchy", "description": "Hierarquia de tempo", "hidden": False, "displayFolder": "", "levels": ["Year", "Quarter", "MonthName", "Date"]}
                ]
            },
        ]

        relationships = [
            {"id": "rel_fSales_dCliente", "fromTable": "fSales", "fromColumn": "CustomerKey", "toTable": "dCliente", "toColumn": "CustomerKey", "cardinality": "Many_One", "crossFilteringBehavior": "SingleDirection", "active": True},
            {"id": "rel_fSales_dProduto", "fromTable": "fSales", "fromColumn": "ProductKey", "toTable": "dProduto", "toColumn": "ProductKey", "cardinality": "Many_One", "crossFilteringBehavior": "SingleDirection", "active": True},
            {"id": "rel_fSales_dCalendario", "fromTable": "fSales", "fromColumn": "OrderDate", "toTable": "dCalendario", "toColumn": "Date", "cardinality": "Many_One", "crossFilteringBehavior": "SingleDirection", "active": True},
        ]

        total_cols = sum(len(t["columns"]) for t in tables)
        total_meas = sum(len(t["measures"]) for t in tables)

        return {
            "modelName": "ContosoRetail_Demo",
            "databaseName": "ContosoRetail_Demo",
            "connectionString": "localhost:demo",
            "tables": tables,
            "relationships": relationships,
            "extractedAt": datetime.utcnow().isoformat(),
            "totalTables": len(tables),
            "totalColumns": total_cols,
            "totalMeasures": total_meas,
            "demo": True
        }
