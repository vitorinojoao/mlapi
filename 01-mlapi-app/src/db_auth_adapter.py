"""db_auth_adapter"""

import os
from sqlalchemy import create_engine, Table, Column, Integer, BigInteger, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker
from flask_security import SQLAlchemyUserDatastore

class AuthBase(DeclarativeBase):
    pass

user_roles = Table(
    "user_roles", AuthBase.metadata,
    Column("user_id", BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", BigInteger, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

class Role(AuthBase):
    __tablename__ = "roles"
    id = Column(BigInteger, primary_key=True)
    name = Column(String(80), unique=True, nullable=False)
    description = Column(String(255))

class User(AuthBase):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    fs_uniquifier = Column(String(64), unique=True, nullable=False, index=True)
    confirmed_at = Column(DateTime(timezone=True))
    last_login_at = Column(DateTime(timezone=True))
    current_login_at = Column(DateTime(timezone=True))
    last_login_ip = Column(String(45))
    current_login_ip = Column(String(45))
    login_count = Column(Integer)
    roles = relationship(Role, secondary=user_roles, backref="users")

class AuthDBAdapter:
    def __init__(self, engine):
        self.engine = engine
        self.session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        self.user_datastore = SQLAlchemyUserDatastore(self.session_factory, User, Role)

    @classmethod
    def from_env(cls):
        url = os.getenv("AUTH_DATABASE_URL")
        if not url:
            pw = cls._read_secret("AUTH_DB_PASSWORD_FILE", "AUTH_DB_PASSWORD")
            url = (f"postgresql+psycopg://{os.getenv('AUTH_DB_USER','auth_app')}:{pw}@"
                   f"{os.getenv('AUTH_DB_HOST','db')}:{os.getenv('AUTH_DB_PORT','5432')}/"
                   f"{os.getenv('AUTH_DB_NAME','auth')}")
        engine = create_engine(url, pool_pre_ping=True,
            pool_size=int(os.getenv("AUTH_DB_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("AUTH_DB_MAX_OVERFLOW", "5")),
            pool_recycle=int(os.getenv("AUTH_DB_POOL_RECYCLE", "1800")))
        return cls(engine)

    @staticmethod
    def _read_secret(file_var, env_var):
        path = os.getenv(file_var)
        if path:
            with open(path, encoding="utf-8") as stream:
                return stream.read().strip()
        return os.getenv(env_var, "")
