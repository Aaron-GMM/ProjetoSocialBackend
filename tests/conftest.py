import pytest
from sqlmodel import Session, SQLModel, create_engine

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def engine():
    """
    Cria o engine e cria todas as tabelas antes dos testes.
    Depois, remove todas as tabelas após os testes.
    """
    engine = create_engine(TEST_DATABASE_URL)
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session(engine):
    """
    Cria uma nova sessão para cada teste envolvida em uma transação.
    Ao final do teste, faz o ROLLBACK, garantindo isolamento total.
    """
    connection = engine.connect()
    transaction = connection.begin()

    session = Session(bind=connection)
    session.begin()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
