from sqlmodel import Session, func, select

from src.domain.models.user import User


def get_user_by_email_case_insensitive(db: Session, email: str) -> User | None:
    """Busca um usuário no banco pelo email."""
    statement = select(User).where(func.lower(User.email) == func.lower(email))
    
    return db.exec(statement).first()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """Busca um usuário pelo ID."""
    statement = select(User).where(User.id == user_id)
    
    return db.exec(statement).first()


def create_user(db: Session, user: User) -> User:
    """Insere um novo usuário no banco."""
    db.add(user)
    db.commit()
    db.refresh(user)

    return user

def get_all_users(db: Session) -> list[User]:
    """Retorna todos os usuários."""
    statement = select(User)
    
    return db.exec(statement).all()


def get_all_users_paginated(db: Session, skip: int = 0, limit: int = 100) -> list[User]:
    """Retorna todos os usuários com paginação."""
    statement = select(User).offset(skip).limit(limit)
    
    return db.exec(statement).all()

def update_user(db: Session, user_id: int, user_data: User) -> User | None:
    """Atualiza um usuário no banco."""
    statement = select(User).where(User.id == user_id)
    user = db.exec(statement).first()
    
    if user:
        for key, value in user_data.model_dump().items():
            setattr(user, key, value)
        db.commit()
        db.refresh(user)
        
    return user

def delete_user(db: Session, user_id: int) -> bool:
    """Deleta um usuário do banco."""
    statement = select(User).where(User.id == user_id)
    user = db.exec(statement).first()
    
    if user:
        db.delete(user)
        db.commit()
        return True
    
    return False

