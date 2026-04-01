Você é um arquiteto de software especialista em Python, Power BI, Analysis Services, modelagem tabular, automação de metadados e desenvolvimento de interfaces web dinâmicas.

Quero que você projete e implemente uma aplicação web dinâmica em **Python** para administração de metadados de um modelo Power BI.

## Objetivo da aplicação

A aplicação deve permitir conectar a um arquivo/modelo Power BI e extrair automaticamente os metadados de **todas as tabelas**, incluindo:

* tabelas
* colunas
* medidas
* hierarquias, se existirem
* descrições
* nomes de exibição
* status de visibilidade (oculto/visível)
* formato, pasta de exibição e propriedades relevantes quando disponíveis

Depois de carregar essas informações, a aplicação deve oferecer um **front-end altamente dinâmico** para manipulação em massa desses metadados.

## Regras técnicas importantes

Considere a arquitetura correta para Power BI:

* Não assumir edição direta binária do `.pbix`.
* Priorizar conexão ao **modelo semântico/tabular** carregado pelo Power BI Desktop ou exposto por **XMLA endpoint**.
* Utilizar abordagem compatível com **Tabular Object Model (TOM)**.
* Caso Python precise interoperar com bibliotecas .NET, estruturar isso da forma mais robusta possível.
* Se necessário, sugerir uso de `pythonnet`, API intermediária em C#, ou serviço backend híbrido Python + .NET.

## O que a aplicação deve fazer

### 1. Conexão

A aplicação deve permitir conexão por dois modos:

1. **Modo local**: conectar ao modelo aberto no Power BI Desktop
2. **Modo remoto**: conectar ao semantic model publicado no Power BI Service via XMLA

A solução deve prever:

* tela de conexão
* validação da conexão
* tratamento de erro
* seleção de workspace/modelo quando aplicável

### 2. Extração de metadados

Após conectar, a aplicação deve ler e estruturar:

* lista de tabelas
* colunas por tabela
* medidas por tabela
* descrições
* hidden / visible
* data type
* format string
* display folder
* expressão DAX da medida, quando permitido
* relacionamentos, se possível
* perspectivas, se existirem
* contagem de objetos por tabela

### 3. Front-end dinâmico

Quero um front-end moderno, fluido e muito dinâmico, com foco em produtividade.

A interface deve permitir:

#### Operações em massa

* ocultar várias colunas ao mesmo tempo
* desocultar várias colunas ao mesmo tempo
* excluir múltiplos objetos selecionados
* alterar descrições em lote
* alterar display folder em lote
* renomear objetos
* filtrar por tabela
* filtrar por tipo de objeto
* pesquisar por nome
* selecionar múltiplos itens com checkbox
* aplicar ações em massa com confirmação

#### Operações individuais

* editar nome
* editar descrição
* alternar oculto/visível
* visualizar propriedades completas
* visualizar DAX de medidas
* editar propriedades permitidas

### 4. Experiência de uso

A aplicação deve ser altamente dinâmica, com:

* interface SPA ou quase SPA
* grid interativo
* filtros instantâneos
* paginação ou virtualização
* ordenação por coluna
* busca em tempo real
* painel lateral de detalhes
* feedback visual de alterações pendentes
* sistema de “salvar alterações”
* opção de desfazer antes da gravação
* mensagens claras de sucesso e erro

### 5. Arquitetura desejada

Proponha uma arquitetura completa contendo:

#### Backend

* Python como backend principal
* framework sugerido: **FastAPI**
* camada de serviço para leitura/escrita de metadados
* camada de integração com TOM/XMLA
* endpoints REST organizados
* suporte a operações em lote
* logs e auditoria de alterações
* controle de transação lógica para aplicar várias mudanças de uma vez

#### Frontend

* pode ser em:

  * React
  * HTML + JS moderno
  * ou outra abordagem que maximize dinamismo
* deve priorizar:

  * performance
  * UX corporativa
  * facilidade de manutenção

### 6. Segurança e governança

A solução deve prever:

* autenticação
* controle de permissões por perfil
* confirmação antes de exclusões
* trilha de auditoria
* backup/exportação do metadata antes de gravar alterações
* modo somente leitura
* ambiente de homologação e produção

### 7. Saídas esperadas

Quero que você entregue:

1. **Arquitetura da solução**
2. **Fluxo técnico da conexão ao modelo Power BI**
3. **Estrutura de pastas do projeto**
4. **Backend em Python**
5. **Estrutura dos endpoints**
6. **Modelo de dados interno para representar tabelas, colunas e medidas**
7. **Front-end dinâmico**
8. **Exemplo de tela principal**
9. **Estratégia para edição em lote**
10. **Estratégia para persistência segura das alterações**
11. **Sugestão de stack completa**
12. **MVP funcional**
13. **Boas práticas de escalabilidade**

## Requisitos adicionais

* A aplicação precisa ser modular e extensível.
* O código deve ser limpo, profissional e pronto para evolução.
* O sistema deve suportar centenas ou milhares de colunas/medidas sem perder fluidez.
* O front-end deve ser responsivo e corporativo.
* O projeto deve ser pensado para uso interno por analistas de BI e administradores de modelos.

## Importante

Quando houver limitação técnica para ler ou alterar `.pbix` diretamente, deixe isso explícito e proponha a abordagem correta baseada no modelo tabular/semantic model.
Priorize uma solução realista, implementável e aderente ao ecossistema Power BI.
