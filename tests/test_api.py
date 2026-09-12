"""Tests for the FastAPI endpoints."""

import sys
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_health(self):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "version" in data


class TestSkillsEndpoints:
    @patch("src.utils.api_data_loader.get_single_skill_roi_data")
    def test_get_all_skills_roi(self, mock_loader):
        mock_loader.return_value = [
            {"skill": "Python", "avg_salary": 130_000, "job_demand_count": 50, "salary_premium": 5_000},
            {"skill": "AWS", "avg_salary": 135_000, "job_demand_count": 40, "salary_premium": 10_000},
        ]
        resp = client.get("/api/v1/skills/roi")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_skills"] == 2
        assert len(data["data"]) == 2

    @patch("src.utils.api_data_loader.get_skill_by_name")
    def test_get_specific_skill(self, mock):
        mock.return_value = {
            "skill": "Python",
            "avg_salary": 130_000,
            "job_demand_count": 50,
            "salary_premium": 5_000,
        }
        resp = client.get("/api/v1/skills/python")
        assert resp.status_code == 200
        assert resp.json()["skill"] == "Python"

    @patch("src.utils.api_data_loader.get_skill_by_name")
    def test_get_skill_not_found(self, mock):
        mock.return_value = None
        resp = client.get("/api/v1/skills/not-a-skill")
        assert resp.status_code == 404

    @patch("src.utils.api_data_loader.get_skill_overlap_data")
    def test_get_overlap(self, mock):
        mock.return_value = [
            {"skill_combo": "Python, AWS", "combo_avg_salary": 150_000,
             "combo_demand_count": 5, "combo_premium": 20_000},
        ]
        resp = client.get("/api/v1/skills/overlap?limit=1")
        assert resp.status_code == 200
        assert resp.json()["total_combos"] == 1

    @patch("src.utils.api_data_loader.compare_skills")
    def test_compare(self, mock):
        mock.return_value = [
            {"skill": "Python", "avg_salary": 130_000, "job_demand_count": 50, "salary_premium": 5_000},
            {"skill": "AWS", "avg_salary": 135_000, "job_demand_count": 40, "salary_premium": 10_000},
        ]
        resp = client.get("/api/v1/skills/compare?skills=python,aws")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_compare_empty(self):
        resp = client.get("/api/v1/skills/compare?skills=")
        assert resp.status_code == 400