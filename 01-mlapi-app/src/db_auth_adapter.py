"""db_auth_adapter"""

import os

from psycopg_pool import ConnectionPool

from sqlalchemy import (
    create_engine,
    Table,
    Column,
    Integer,
    BigInteger,
    String,
    Boolean,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker
from flask_security import SQLAlchemyUserDatastore


class DBAuthAdapter:
    """Object to connect and communicate with an auth database"""

    def __init__(
        self,
        db_host,
        db_port,
        db_name,
        db_user,
        db_password,
        db_pool_min,
        db_pool_max,
        db_pool_workers,
        db_pool_timeout,
    ):
        try:
            db_host = str(db_host)
            db_port = str(int(db_port))
            db_name = str(db_name)
            db_user = str(db_user)
            db_password = str(db_password)

        except Exception as e:
            raise ValueError(
                "The DB Adapter requires valid connection credentials"
            ) from e

        ## ----------------------------------------

        try:
            db_pool_min = int(db_pool_min)
            db_pool_max = int(db_pool_max)
            db_pool_workers = int(db_pool_workers)
            db_pool_timeout = int(db_pool_timeout)

        except Exception as e:
            raise ValueError(
                "The DB Adapter requires a valid connection pool configuration"
            ) from e

        ## ----------------------------------------

        self.pool = ConnectionPool(
            conninfo=(
                f"host={db_host}"
                f" port={db_port}"
                f" dbname={db_name}"
                f" user={db_user}"
                f" password={db_password}"
            ),
            min_size=db_pool_min,
            max_size=db_pool_max,
            num_workers=db_pool_workers,
            timeout=db_pool_timeout,
            kwargs={"autocommit": False},
            open=True,
        )

    ## ----------------------------------------

    def close(self):
        self.pool.close()

    ## ----------------------------------------


class AuthBase(DeclarativeBase):
    pass


user_roles = Table(
    "user_roles",
    AuthBase.metadata,
    Column(
        "user_id",
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "role_id",
        BigInteger,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
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
            url = (
                f"postgresql+psycopg://{os.getenv('AUTH_DB_USER','auth_app')}:{pw}@"
                f"{os.getenv('AUTH_DB_HOST','db')}:{os.getenv('AUTH_DB_PORT','5432')}/"
                f"{os.getenv('AUTH_DB_NAME','auth')}"
            )
        engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=int(os.getenv("AUTH_DB_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("AUTH_DB_MAX_OVERFLOW", "5")),
            pool_recycle=int(os.getenv("AUTH_DB_POOL_RECYCLE", "1800")),
        )
        return cls(engine)

    @staticmethod
    def _read_secret(file_var, env_var):
        path = os.getenv(file_var)
        if path:
            with open(path, encoding="utf-8") as stream:
                return stream.read().strip()
        return os.getenv(env_var, "")
