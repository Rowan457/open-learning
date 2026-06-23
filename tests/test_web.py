"""Tests for Web UI — FastAPI app and REST API."""

import pytest
from unittest.mock import patch, MagicMock


# ── Fixtures ────────────────────────────────────────────────


@pytest.fixture
def client():
    """Create a FastAPI test client."""
    from fastapi.testclient import TestClient
    from openlearning.web.app import create_app

    app = create_app()
    return TestClient(app)


# ── Health & Dashboard ──────────────────────────────────────


class TestHealthEndpoints:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_dashboard(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "OpenLearning" in resp.text
        assert "仪表盘" in resp.text

    def test_projects_page(self, client):
        resp = client.get("/projects")
        assert resp.status_code == 200
        assert "项目管理" in resp.text

    def test_plugins_page(self, client):
        resp = client.get("/plugins")
        assert resp.status_code == 200
        assert "插件管理" in resp.text


# ── Project API ─────────────────────────────────────────────


class TestProjectAPI:
    def test_list_projects_empty(self, client):
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_project(self, client):
        resp = client.post("/api/projects", json={
            "title": "Test Project",
            "description": "A test project",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Test Project"
        assert "id" in data

    def test_get_project_not_found(self, client):
        resp = client.get("/api/projects/nonexistent")
        assert resp.status_code == 404

    def test_create_and_get_project(self, client):
        # Create
        create_resp = client.post("/api/projects", json={"title": "My Project"})
        project_id = create_resp.json()["id"]

        # Get
        get_resp = client.get(f"/api/projects/{project_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["title"] == "My Project"

    def test_update_project(self, client):
        # Create
        create_resp = client.post("/api/projects", json={"title": "Original"})
        project_id = create_resp.json()["id"]

        # Update
        update_resp = client.put(f"/api/projects/{project_id}", json={"title": "Updated"})
        assert update_resp.status_code == 200
        assert update_resp.json()["title"] == "Updated"

    def test_delete_project(self, client):
        # Create
        create_resp = client.post("/api/projects", json={"title": "To Delete"})
        project_id = create_resp.json()["id"]

        # Delete
        delete_resp = client.delete(f"/api/projects/{project_id}")
        assert delete_resp.status_code == 200
        assert delete_resp.json()["status"] == "deleted"

        # Verify gone
        get_resp = client.get(f"/api/projects/{project_id}")
        assert get_resp.status_code == 404

    def test_delete_not_found(self, client):
        resp = client.delete("/api/projects/nonexistent")
        assert resp.status_code == 404


# ── Resource API ────────────────────────────────────────────


class TestResourceAPI:
    def test_list_resources_not_found(self, client):
        resp = client.get("/api/projects/nonexistent/resources")
        assert resp.status_code == 404

    def test_list_resources_empty(self, client):
        # Create project
        create_resp = client.post("/api/projects", json={"title": "Empty"})
        project_id = create_resp.json()["id"]

        # List resources
        resp = client.get(f"/api/projects/{project_id}/resources")
        assert resp.status_code == 200
        assert resp.json() == []


# ── Plugin API ──────────────────────────────────────────────


class TestPluginAPI:
    def test_list_plugins(self, client):
        resp = client.get("/api/plugins")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_enable_plugin_not_found(self, client):
        resp = client.put("/api/plugins/nonexistent/enable")
        assert resp.status_code == 404

    def test_disable_plugin_not_found(self, client):
        resp = client.put("/api/plugins/nonexistent/disable")
        assert resp.status_code == 404

    def test_reload_plugins(self, client):
        resp = client.post("/api/plugins/reload")
        assert resp.status_code == 200
        assert "count" in resp.json()


# ── Export API ───────────────────────────────────────────────


class TestExportAPI:
    def test_export_no_graph(self, client):
        """Export should fail gracefully when no knowledge graph exists."""
        create_resp = client.post("/api/projects", json={"title": "No Graph"})
        project_id = create_resp.json()["id"]

        resp = client.get(f"/api/projects/{project_id}/export?format=markdown")
        assert resp.status_code == 404


# ── App Creation ────────────────────────────────────────────


class TestAppCreation:
    def test_create_app(self):
        from openlearning.web.app import create_app

        app = create_app()
        assert app.title == "OpenLearning Web UI"
        assert app.version == "0.1.0"

    def test_api_docs_available(self, client):
        resp = client.get("/api/docs")
        assert resp.status_code == 200
