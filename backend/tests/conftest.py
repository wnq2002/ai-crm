"""Pytest 共享夹具。

环境变量必须在导入应用模块之前设置（settings 经 lru_cache 只实例化一次）。
测试数据库：本地 PostgreSQL `ai_crm_test`，每测试前 TRUNCATE 保持隔离。
"""

import os

os.environ["DATABASE_URL"] = "postgresql+psycopg://wnq@localhost:5432/ai_crm_test"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["ADMIN_INITIAL_PASSWORD"] = ""  # 测试环境禁用自动种子
os.environ["LOGIN_MAX_ATTEMPTS"] = "5"
os.environ["LOGIN_WINDOW_SECONDS"] = "300"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.auth.rate_limit import login_rate_limiter  # noqa: E402
from app.core.db import Base, SessionLocal, engine, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = SessionLocal()
    with session.begin():
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))
    yield session
    session.close()


@pytest.fixture
def client_factory(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    def _make(raise_server_exceptions: bool = True) -> TestClient:
        return TestClient(app, raise_server_exceptions=raise_server_exceptions)

    yield _make
    app.dependency_overrides.clear()


@pytest.fixture
def client(client_factory):
    return client_factory()


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    login_rate_limiter.reset_all()
    yield
