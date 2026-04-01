# Power BI Metadata Editor

Aplicacao web para administrar metadados de modelos Power BI (tabelas, colunas, medidas, hierarquias, relacionamentos) com foco em edicao em lote e produtividade.

## 1) O que este projeto faz

- Conecta ao modelo semantico do Power BI Desktop (local) ou Power BI Service/Fabric (remoto via XMLA).
- Extrai metadados do modelo e mostra em uma interface web dinamica.
- Permite editar metadados de forma individual e em lote.
- Trabalha com alteracoes pendentes (cache) e aplica no modelo apenas quando voce clica em `Salvar`.
- Mantem trilha de auditoria em `backend/audit.log`.

Importante:
- Este projeto nao edita o arquivo `.pbix` binario diretamente.
- A edicao ocorre no modelo tabular em memoria (TOM/XMLA), que e o caminho correto no ecossistema Power BI.

## 2) Arquitetura resumida

- Backend: FastAPI (Python)
- Frontend: HTML + JS (Tabulator + Bootstrap)
- Integracao com Power BI: `pythonnet` + assemblies `.NET` do TOM/AMO

Fluxo:
1. Frontend chama API (`/api/...`).
2. API altera cache local e cria pendencias.
3. No `Salvar`, backend aplica tudo em lote (`SaveChanges` unico quando possivel).

## 3) Pre-requisitos

## Sistema
- Windows (recomendado, pois a deteccao local de porta do Power BI Desktop usa caminhos/processos Windows).
- Power BI Desktop instalado.

## Python
- Python 3.13 (ou versao compativel com as dependencias).
- `pip` atualizado.

## Dependencias TOM/AMO
Para conexao real (fora do modo demonstracao), voce precisa de:
- `pythonnet==3.0.5` (ja no `backend/requirements.txt`)
- DLL `Microsoft.AnalysisServices.Tabular.dll` disponivel em alguma das localizacoes conhecidas.

O backend procura essa DLL em caminhos comuns, por exemplo:
- `C:\Program Files\Microsoft.NET\ADOMD.NET\160\...`
- `C:\Program Files\Microsoft SQL Server\160\SDK\Assemblies\...`
- `C:\Program Files\Microsoft SQL Server Management Studio 21\Release\Common7\IDE\...`

Se precisar, defina manualmente:

```powershell
$env:TOM_ASSEMBLY_PATH = "C:\caminho\Microsoft.AnalysisServices.Tabular.dll"
```

## 4) Instalacao e execucao

## Opcao A (rapida)
Na raiz do projeto:

```powershell
.\start.bat
```

Esse script:
1. entra em `backend/`
2. instala requirements
3. sobe o servidor em `http://localhost:8000`

## Opcao B (manual)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

Depois abra no navegador:
- `http://localhost:8000`

## 5) Como usar a aplicacao

## Conectar
1. Clique em `Conectar`.
2. Escolha:
- `Power BI Desktop` (local, detecta porta automaticamente)
- `Power BI Service` (workspace/modelo)

## Editar
- Grade principal: editar descricao, formato, pasta, oculto/visivel.
- Barra de selecao: ocultar/mostrar varios objetos e mover pasta em lote.
- Menu de contexto na tabela (botao direito): renomear, excluir, ocultar/mostrar tabela inteira (incluindo objetos internos).

## Persistir
- `Salvar`: aplica pendencias no modelo.
- `Descartar`: volta para o snapshot anterior sem gravar.
- `Exportar`: gera backup dos metadados (JSON).

## 6) Modo real vs modo demonstracao

A API entra em modo demo quando nao consegue conexao TOM real.

Sinais tipicos:
- "Power BI Desktop nao encontrado. Usando modo demonstracao."
- "pythonnet/AMO nao disponivel para conexao TOM..."

No modo demo, a UI funciona com dados ficticios para desenvolvimento.

## 7) Performance (aplicar alteracoes)

O projeto ja esta otimizado para cenarios massivos:
- commit em lote com um unico `SaveChanges` quando possivel
- compactacao de pendencias redundantes antes do commit
- ocultar tabela inteira via evento sintetico unico (`__set_hidden_all__`)

Mesmo assim, em modelos grandes, o Power BI Desktop pode demorar alguns segundos para processar internamente apos `SaveChanges`.

## 8) Configuracao por `.env`

Arquivo: `backend/.env` (opcional)

Exemplo:

```env
APP_NAME=Power BI Metadata Editor
SECRET_KEY=troque_esta_chave
ACCESS_TOKEN_EXPIRE_MINUTES=480
READ_ONLY_MODE=false
AUDIT_LOG_PATH=./audit.log
```

Observacoes:
- `READ_ONLY_MODE=true` bloqueia escrita (`commit`, update, batch etc).
- `SECRET_KEY` deve ser fixa em ambiente real.

## 9) Autenticacao

- Endpoint de token: `POST /api/auth/token`
- Usuarios MVP hardcoded:
- `admin / admin`
- `viewer / viewer`

Em modo dev, chamadas sem token sao aceitas como usuario `dev` (admin).

## 10) API principal

## Conexao
- `GET /api/connections/status`
- `POST /api/connections/connect`
- `POST /api/connections/disconnect`
- `GET /api/connections/databases`

## Metadados
- `GET /api/metadata/`
- `GET /api/metadata/objects`
- `POST /api/metadata/update`
- `GET /api/metadata/pending`
- `POST /api/metadata/commit`
- `POST /api/metadata/discard`
- `POST /api/metadata/tables/{table_id}/rename`
- `POST /api/metadata/tables/{table_id}/hidden`
- `POST /api/metadata/tables/{table_id}/delete`

## Lote
- `POST /api/batch/update`
- `POST /api/batch/hide`
- `POST /api/batch/show`
- `POST /api/batch/set-display-folder`
- `POST /api/batch/set-description`

## 11) Instalando o MCP do Power BI

Este projeto funciona sem MCP. MCP e opcional, usado para integrar AI agents diretamente com ferramentas de modelagem Power BI.

Existem dois MCPs oficiais relacionados:

1. Power BI Modeling MCP (local, modelagem)
- Repo oficial: `https://github.com/microsoft/powerbi-modeling-mcp`
- Hub Microsoft Learn: `https://learn.microsoft.com/en-us/power-bi/developer/mcp/`

2. Power BI Remote MCP (HTTP endpoint para query)
- Endpoint: `https://api.fabric.microsoft.com/v1/mcp/powerbi`
- Guia: `https://learn.microsoft.com/en-us/power-bi/developer/mcp/remote-mcp-server-get-started`

## 11.1) Modeling MCP - instalacao recomendada (VS Code)
Conforme documentacao oficial:
1. Instale VS Code.
2. Instale GitHub Copilot + GitHub Copilot Chat.
3. Instale extensao "Power BI Modeling MCP".
4. Abra o chat do Copilot e confirme o server `powerbi-modeling-mcp` ativo.

## 11.2) Modeling MCP - instalacao manual
Passos oficiais (resumo):
1. Baixe o pacote VSIX da extensao `powerbi-modeling-mcp`.
2. Extraia para uma pasta local, por exemplo `C:\MCPServers\PowerBIModelingMCP`.
3. Rode:

```powershell
C:\MCPServers\PowerBIModelingMCP\extension\server\powerbi-modeling-mcp.exe --start
```

4. Registre no cliente MCP usando `stdio`.

Exemplo de configuracao generica:

```json
{
  "servers": {
    "powerbi-modeling-mcp": {
      "type": "stdio",
      "command": "C:\\MCPServers\\PowerBIModelingMCP\\extension\\server\\powerbi-modeling-mcp.exe",
      "args": [
        "--start"
      ],
      "env": {}
    }
  }
}
```

## 11.3) Remote MCP - configuracao manual

```json
{
  "servers": {
    "powerbi-remote": {
      "type": "http",
      "url": "https://api.fabric.microsoft.com/v1/mcp/powerbi"
    }
  }
}
```

Prerequisitos importantes para o Remote MCP (segundo Microsoft Learn):
- admin do tenant deve habilitar o endpoint MCP no Power BI
- voce precisa de permissao `Build` no semantic model
- o cliente MCP precisa suportar servidores HTTP

## 12) Troubleshooting

## Erro: "Power BI Desktop nao encontrado. Usando modo demonstracao."
Checklist:
1. Abra o Power BI Desktop com um arquivo carregado.
2. Aguarde o modelo terminar de carregar.
3. Clique em conectar novamente.
4. Verifique se processos `PBIDesktop` e `msmdsrv` existem.

## Erro: "No module named 'clr'"
Causa: `pythonnet` nao instalado no ambiente Python ativo.

Correcao:

```powershell
python -m pip install pythonnet==3.0.5
```

Depois reinicie o backend.

## Erro: TOM/AMO indisponivel
Causa: DLL `Microsoft.AnalysisServices.Tabular.dll` nao encontrada.

Correcao:
1. Instale fonte da DLL (ex.: SSMS/ADOMD.NET/SDK SQL Server).
2. Defina `TOM_ASSEMBLY_PATH` apontando para a DLL.
3. Reinicie terminal e backend.

## Erro ao instalar requirements no Python 3.13
Use:

```powershell
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r backend/requirements.txt
```

## 13) Estrutura de pastas

```text
.
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   └── app/
│       ├── api/
│       ├── core/
│       ├── models/
│       └── services/
├── frontend/
│   ├── index.html
│   ├── css/
│   └── js/
└── start.bat
```

## 14) Boas praticas para uso em producao

- Sempre faca backup antes de gravar mudancas em massa.
- Use `READ_ONLY_MODE=true` em ambientes de homologacao quando necessario.
- Troque credenciais/chaves padrao (`SECRET_KEY`, usuarios MVP).
- Restrinja CORS e autentique todas as chamadas em producao.
- Revise `audit.log` periodicamente.

## 15) Observacao final

Se voce quiser, eu posso gerar uma versao "README Operacional" separada (mais curta, tipo runbook) so com:
- setup
- validacao de conexao
- comandos de diagnostico
- recuperacao de falhas

