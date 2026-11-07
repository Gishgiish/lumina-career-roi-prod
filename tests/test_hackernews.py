# tests/test_hackernews.py
"""Regression tests for the HackerNews adapter's currency contract."""

from src.ingestion.sources.hackernews import HackerNewsSource


def _source_with_comment(monkeypatch, text: str) -> HackerNewsSource:
    source = HackerNewsSource(config={})
    monkeypatch.setattr(
        source,
        "_fetch_threads",
        lambda: [{"objectID": 1, "created_at": "2025-06-01T00:00:00Z"}],
    )
    monkeypatch.setattr(source, "_fetch_comments", lambda thread_id: [10])
    monkeypatch.setattr(
        source,
        "_fetch_comment",
        lambda comment_id: {"text": text, "time": 1748736000},
    )
    return source


def test_does_not_force_usd_on_free_text_salary(monkeypatch):
    """HackerNews salaries may be EUR or GBP; the symbol must drive currency."""
    source = _source_with_comment(monkeypatch, "Acme | Engineer | Berlin | €80k")

    batch = source.fetch()

    assert len(batch.jobs) == 1
    assert batch.jobs[0].salary_raw == "€80k"
    assert batch.jobs[0].salary_currency is None
