from sqlmodel import Session, select, insert

from src.domain.models.user import User
from src.infrastructure.database.connection import engine

class UserRepository:
    """
    Repository para operações relacionadas aos usuários.

    Esta classe fornece métodos para realizar operações CRUD no banco de dados
    para a entidade User, utilizando SQLModel e SQLAlchemy.
    """

    def __init__(self):
        pass
    
    def create_user(self, user: User) -> User:
        """
        Cria um novo usuário no banco de dados.

        Args:
            user: Objeto User com os dados do usuário a ser criado.

        Returns:
            User: Objeto User criado com o ID gerado pelo banco.
        """
        with Session(engine) as session:
            insert_statement = insert(User).values(**user.model_dump())
            session.exec(insert_statement)
            session.commit()
            session.refresh(user)
            return user
    
    def get_user_by_id(self, user_id: int) -> User | None:
        """
        Busca um usuário pelo ID.

        Args:
            user_id: ID do usuário a ser buscado.

        Returns:
            User | None: Objeto User se encontrado, None caso contrário.
        """
        with Session(engine) as session:
            statement = select(User).where(User.id == user_id)
            result = session.exec(statement)
            return result.first()
    
    def get_user_by_email(self, email: str) -> User | None:
        """
        Busca um usuário pelo email.

        Args:
            email: Email do usuário a ser buscado.

        Returns:
            User | None: Objeto User se encontrado, None caso contrário.
        """
        with Session(engine) as session:
            statement = select(User).where(User.email == email)
            result = session.exec(statement)
            return result.first()

    def get_user_by(self, attribute: str, value: str | int) -> User | None:
        """
        Busca um usuário por um atributo específico.

        Args:
            attribute: Nome do atributo do User para buscar (ex: 'email', 'matricula').
            value: Valor do atributo a ser buscado.

        Returns:
            User | None: Objeto User se encontrado, None caso contrário.

        Raises:
            ValueError: Se o atributo informado não existir no modelo User.
        """
        if not hasattr(User, attribute):
            raise ValueError(f"Invalid attribute: {attribute}")
            
        with Session(engine) as session:
            statement = select(User).where(getattr(User, attribute) == value)
            result = session.exec(statement)
            return result.first()
    
    def get_all_users(self) -> list[User]:
        """
        Busca todos os usuários do banco de dados.

        Returns:
            list[User]: Lista com todos os usuários cadastrados.
        """
        with Session(engine) as session:
            statement = select(User)
            result = session.exec(statement)
            return result.all()