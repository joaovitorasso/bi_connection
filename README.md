# Power BI Metadata Editor

Editor web para metadados de modelos Power BI.

## O que ele faz

- Conecta ao modelo aberto no Power BI Desktop.
- Lista tabelas, colunas, medidas, hierarquias e relacionamentos.
- Permite editar em lote:
- ocultar/mostrar objetos
- alterar pasta de exibicao
- alterar descricao
- renomear/excluir/ocultar tabela inteira
- So grava no modelo quando voce clica em `Salvar`.

Importante:
- Ele nao edita o arquivo `.pbix` diretamente.
- A edicao acontece no modelo tabular carregado pelo Power BI.

## Requisitos

- Windows
- Power BI Desktop instalado e com um arquivo aberto
- Python 3.13

## Como rodar (mais facil)

Na raiz do projeto:

```powershell
.\start.bat
```

Depois abra:

```text
http://localhost:8000
```

## Rodar manualmente (opcional)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r requirements.txt
python main.py
```

## Como usar

1. Clique em `Conectar`.
2. Escolha `Power BI Desktop`.
3. Faça as alteracoes na grade.
4. Clique em `Salvar` para aplicar no modelo.

Enquanto voce nao salvar, tudo fica como alteracao pendente.

## Erros comuns

## "Power BI Desktop nao encontrado. Usando modo demonstracao."

- Abra o Power BI Desktop com o arquivo carregado.
- Aguarde terminar de carregar.
- Tente conectar novamente.

## "No module named 'clr'"

Instale o `pythonnet`:

```powershell
python -m pip install pythonnet==3.0.5
```

Depois reinicie o backend.

## "pythonnet/AMO nao disponivel..."

A DLL do TOM nao foi encontrada.

Se precisar, defina o caminho manualmente:

```powershell
$env:TOM_ASSEMBLY_PATH = "C:\caminho\Microsoft.AnalysisServices.Tabular.dll"
```

## Arquivos principais

- `backend/main.py`: inicializacao da API
- `backend/app/services/tom_service.py`: conexao com Power BI/TOM
- `backend/app/services/metadata_service.py`: cache e commit de alteracoes
- `frontend/index.html`: tela principal
- `frontend/js/app.js`: fluxo da interface

## Observacao

Este projeto nao depende de MCP e o README foi mantido sem essa etapa.

