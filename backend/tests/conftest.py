import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["UPLOAD_DIR"] = "/tmp/bistate-test-uploads"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app as fastapi_app
import app.models  # noqa: F401 - register model metadata


@pytest.fixture(autouse=True)
def reset_database() -> None:
    from pathlib import Path
    import shutil

    shutil.rmtree(Path(os.environ["UPLOAD_DIR"]), ignore_errors=True)
    Base.metadata.drop_all(bind=engine)
    shutil.rmtree(Path(os.environ["UPLOAD_DIR"]), ignore_errors=True)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> TestClient:
    return TestClient(fastapi_app)
