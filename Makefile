.PHONY: setup run test lint format migrate-generate migrate-apply

setup:
	@echo "Instalando dependências com uv..."
	uv venv --allow-existing && uv pip install -e ".[dev]"

run:
	docker-compose up --build

test:
	uv run pytest

lint:
	uv run ruff check src tests

format:
	uv run ruff check --fix src tests
	uv run ruff format src tests

migrate-generate:
	@read -p "Mensagem da migration: " msg; \
	uv run alembic revision --autogenerate -m "$$msg"

migrate-apply:
	uv run alembic upgrade head

# --- Comandos Adicionais ---

build:
	@echo "Compilando (build) o projeto usando uv..."
	uv build

db-up:
	@echo "Subindo os containers de banco de dados..."
	docker-compose up -d db

db-down:
	@echo "Derrubando os containers e limpando volumes (CUIDADO: apaga dados locais)..."
	docker-compose down -v

test-alembic: db-up
	@echo "Aguardando o banco ficar pronto..."
	sleep 5
	@echo "Testando se o Alembic consegue gerar uma migration (Dry Run)..."
	uv run alembic upgrade head
	@echo "Tudo certo com o Alembic!"

test-all: lint format test
	@echo "Testes e validações de código completados com sucesso!"
