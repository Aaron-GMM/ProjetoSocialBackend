from sqlmodel import SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    # TODO Equipe: Adicionem os outros campos necessários (nome, etc)
