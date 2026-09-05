# Caça Placa - Backend (API)

A API oficial do projeto Caça Placa, focada em mapeamento colaborativo e georreferenciado de sinalizações de trânsito na região de Quixadá.

## Arquitetura do Projeto
A arquitetura do projeto foi ajustada para ser ainda mais direta, mantendo os princípios de separação, mas eliminando níveis desnecessários de aninhamento. Utilizamos o `SQLModel` como nossa ponte unificada entre regras (Pydantic) e acesso a dados (SQLAlchemy).

A estrutura atual em `src/` segue:
- **`src/api/`**: Camada de roteamento, abrigando as rotas (`routes/`) e *endpoints* da FastAPI.
- **`src/application/`**:*Schemas* para Requests/Responses e a lógica de transição.
- **`src/core/`**: Configurações globais e tratamento de exceções.
- **`src/domain/`**: Entidades de banco/negócio representadas via `SQLModel` (`models.py`).
- **`src/infrastructure/`**: Camada de persistência (conexão `connection.py` e abstração de `repositories.py` no PostGIS) e *Storage* externo (ex: `minio_client.py`).

## Stack Tecnológica
* **Linguagem:** Python 3.12+
* **Framework:** FastAPI
* **ORM:** SQLModel
* **Banco de Dados:** PostgreSQL + PostGIS (GeoAlchemy2) - Usando `postgis/postgis:15-3.3-alpine`
* **Migrations:** Alembic
* **Package Manager:** `uv`
* **Testes:** Pytest (Meta  de > 85% coverage)

## Comandos Rápidos (Makefile)

 Facilitar o desenvolvimento e a configuração :

| Comando | Descrição |
|---------|-----------|
| `make setup` | Instala todas as dependências do projeto usando `uv` (recria a venv se necessário). |
| `make build` | Compila o projeto (`uv build`). |
| `make run` | Sobe a aplicação e o banco local integrado através do Docker Compose. |
| `make db-up` | Sobe apenas o container do banco de dados (PostGIS) em plano de fundo. |
| `make db-down` |  Derruba o banco de dados e apaga os volumes locais (zerando os dados). |
| `make test-alembic` | Sobe o banco temporário e testa a comunicação e execução das migrações do Alembic. |
| `make migrate-generate` | Cria uma nova migração a partir do estado atual dos modelos (pede mensagem). |
| `make migrate-apply` | Aplica as migrações criadas no banco de dados. |
| `make lint` / `make format` | Executa o Ruff para checagem e formatação do código Python. |
| `make test-all` | Roda sequencialmente: `lint`, `format` e valida as regras no `pytest` (e a meta de 85% de coverage). |

## Como Iniciar o Desenvolvimento

1. Crie o ambiente virtual e instale os pacotes:
   ```bash
   make setup
   ```
2. Suba o banco de dados e teste as migrations:
   ```bash
   make test-alembic
   ```
3. Valide o código com os testes:
   ```bash
   make test-all
   ```
