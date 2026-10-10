# Caça Placa - Backend (API)

A API oficial do projeto Caça Placa, focada em mapeamento colaborativo e georreferenciado de sinalizações de trânsito na região de Quixadá.

## Arquitetura do Projeto
A arquitetura do projeto segue princípios de separação de responsabilidades, eliminando níveis de aninhamento desnecessários. O `SQLModel` é utilizado como ponte unificada entre regras de validação (Pydantic) e acesso a dados (SQLAlchemy).

A estrutura atual (`src/`) está organizada em:
- **`api/`**: Camada de roteamento (`routes/`), *endpoints* FastAPI e middlewares
- **`application/`**: *Schemas* (DTOs) para Requests/Responses (separando o que entra/sai da API do modelo de banco).
- **`core/`**: Configurações globais (`settings`), tratamento de exceções, e lógicas core de segurança (geração e validação de senhas, JWT Hashing, RBAC).
- **`domain/`**: Entidades de banco e domínio representadas via `SQLModel` (`models.py`, `enums/`).
- **`infrastructure/`**: Camada de infraestrutura externa, incluindo persistência (conexão assíncrona ao PostgreSQL/PostGIS) e *Serviços* (disparo de e-mails, client MinIO para Object Storage).

## Stack Tecnológica
* **Linguagem:** Python 3.12+
* **Framework:** FastAPI
* **ORM:** SQLModel (Pydantic V2 + SQLAlchemy 2)
* **Banco de Dados:** PostgreSQL + PostGIS (GeoAlchemy2 e `asyncpg`) - Imagem `postgis/postgis:15-3.3-alpine`
* **Migrations:** Alembic
* **Package Manager:** `uv`
* **Testes:** Pytest (Meta de > 85% coverage com banco isolado)

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

## Variáveis de Ambiente (.env)
Antes de rodar o projeto, crie um arquivo `.env` na raiz do projeto.
Abaixo um exemplo de como o arquivo deve ser estruturado (copie este conteúdo e ajuste conforme necessário):

```env
# Configurações do Banco de Dados
DATABASE_URL="postgresql+asyncpg://seu_usuario:sua_senha@localhost:5432/nome_do_banco"
POSTGRES_USER=seu_usuario
POSTGRES_PASSWORD=sua_senha
POSTGRES_DB=nome_do_banco

# Configurações de Segurança e JWT
SECRET_KEY="SUA_CHAVE_SECRETA_AQUI"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=60
RESET_TOKEN_EXPIRE_MINUTES=15

# Integração com Frontend (Base para envio de E-mails e CORS)
FRONTEND_URL="http://localhost:5173"
```

## Como Iniciar o Desenvolvimento (Passo a Passo)

Siga rigorosamente a sequência abaixo para preparar seu ambiente, estruturar o banco de dados e rodar a aplicação localmente de forma correta:

1. **Configuração de Variáveis de Ambiente:**
   Crie o arquivo `.env` na raiz do projeto copiando o conteúdo do bloco de código acima.
   *(Edite o `.env` se precisar alterar alguma porta ou senha local).*

2. **Instalação de Dependências:**
   Crie o ambiente virtual e instale os pacotes (utilizamos o `uv`):
   ```bash
   make setup
   ```

3. **Subir o Banco de Dados (PostGIS):**
   Inicie o container do PostgreSQL em plano de fundo:
   ```bash
   make db-up
   ```

4. **Aplicar as Migrations (Estruturar o Banco):**
   Com o banco rodando, aplique as migrações para criar as tabelas no PostGIS:
   ```bash
   make migrate-apply
   ```

5. **Testar a Aplicação (Recomendado):**
   Valide se o código e a comunicação com o banco estão 100% funcionais:
   ```bash
   make test-all
   ```

6. **Rodar a API:**
   Para desenvolver rodando a API direto no seu terminal (ideal para debugging):
   ```bash
   uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   *Alternativa (Docker Completo):* Você pode subir a aplicação e o banco juntos via Docker Compose:
   ```bash
   make run
   ```

**Acessando a Documentação:**
Com a API rodando, acesse o Swagger UI interativo em: [http://localhost:8000/docs](http://localhost:8000/docs)
