# tests/test_adzuna.py
"""Regression tests for the Adzuna adapter's salary/currency contract."""

from src.ingestion.sources import adzuna
from src.ingestion.sources.adzuna import AdzunaSource


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_fetch_emits_numeric_salary_with_iso_currency(monkeypatch):
    """Adzuna must not prefix every salary with '$'.

    The adapter knows the country currency; the salary string should be plain
    numbers so ``_parse_salary`` can apply that ISO code instead of guessing USD
    from a misleading dollar sign.
    """
    payload = {
        "results": [
            {
                "id": "123",
                "title": "Software Engineer",
                "description": "Build things",
                "created": "2025-06-01T10:00:00Z",
                "salary_min": 70000,
                "salary_max": 90000,
                "location": {"display_name": "Somewhere", "area": None},
                "category": {"label": "IT"},
                "redirect_url": "https://example.com/job/123",
                "company": {"display_name": "Example Ltd"},
            }
        ],
        "count": 1,
    }

    monkeypatch.setattr(adzuna.httpx, "get", lambda *args, **kwargs: _FakeResponse(payload))

    source = AdzunaSource(config={"app_id": "test", "app_key": "test"})
    batch = source.fetch()

    jobs = {job.country: job for job in batch.jobs if job.country}

    for country, currency in (("GB", "GBP"), ("IN", "INR"), ("DE", "EUR"), ("US", "USD")):
        job = jobs[country]
        assert job.salary_currency == currency
        assert job.salary_raw == "70000 - 90000"
        assert "$" not in job.salary_raw
