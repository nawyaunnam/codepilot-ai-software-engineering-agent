import io
import zipfile

import pytest
from codepilot import auth, main
from codepilot.config import settings
from codepilot.ingestion import github_archive, unpack
from codepilot.models import Base
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def archive(entries):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as z:
        for name, value in entries.items():
            z.writestr(name, value)
    return data.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(main, "SessionLocal", sessionmaker(engine))
    monkeypatch.setattr(settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(settings, "admin_password", "long-test-password")
    monkeypatch.setattr(settings, "jwt_secret", "test-secret-" * 4)
    monkeypatch.setattr(settings, "embedding_provider", "disabled")
    auth._attempts.clear()
    return TestClient(main.app)


def sign_in(client):
    response = client.post("/auth/login", json={"username": "admin", "password": "long-test-password"})
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    return response.json()["access_token"]


def test_auth_import_query_and_logout(client):
    assert client.get("/api/repositories").status_code == 401
    assert client.post("/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401
    sign_in(client)
    data = archive({"project/auth.py": "def authenticate(user):\n    return bool(user)\n"})
    response = client.post(
        "/api/repositories/upload", content=data, headers={"Content-Type": "application/zip"}
    )
    assert response.status_code == 201, response.text
    repo_id = response.json()["id"]
    result = client.post(f"/api/repositories/{repo_id}/query", json={"question": "authenticate"}).json()
    assert result["citations"][0]["path"] == "auth.py"
    assert client.get("/api/repositories/999/graph").status_code == 404
    client.post("/auth/logout")
    assert client.get("/api/repositories").status_code == 401


def test_csrf_and_bearer(client):
    token = sign_in(client)
    assert (
        client.post(
            "/api/repositories",
            json={"name": "x", "path": "/workspace"},
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    client.cookies.clear()
    assert client.get("/api/repositories", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert client.get("/api/repositories", headers={"Authorization": "Bearer broken"}).status_code == 401


@pytest.mark.parametrize("name", ["../escape.py", "/absolute.py", "repo/../../escape", "repo\\escape.py"])
def test_zip_traversal_rejected(tmp_path, monkeypatch, name):
    monkeypatch.setattr(settings, "workspace_root", str(tmp_path))
    with pytest.raises(ValueError):
        unpack(archive({name: "x"}))
    assert list(tmp_path.iterdir()) == []


def test_zip_size_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(settings, "max_repository_bytes", 100)
    with pytest.raises(ValueError):
        unpack(archive({"file.py": "x" * 101}))


def test_github_rejects_untrusted_hosts():
    with pytest.raises(ValueError):
        github_archive("http://localhost/private", "main")
    with pytest.raises(ValueError):
        github_archive("https://github.com/a/b", "../../private")


def test_login_rate_limit(client):
    for _ in range(5):
        assert client.post("/auth/login", json={"username": "admin", "password": "bad"}).status_code == 401
    assert client.post("/auth/login", json={"username": "admin", "password": "bad"}).status_code == 429
