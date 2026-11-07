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


def test_html_paragraphs_do_not_become_salary_text(monkeypatch):
    """Algolia returns HTML; only an explicit salary token may reach salary_raw."""
    text = (
        "Acme | Engineer | Remote | $190k USD + equity"
        "<p>We build things. <a href=\"https://x.test/jobs\">Apply</a>"
        "<p>More details."
    )
    source = _source_with_comment(monkeypatch, text)

    job = source.fetch().jobs[0]

    assert job.salary_raw == "$190k"
    assert job.title == "Engineer"
    assert "<p>" not in job.description
    assert "<a" not in job.description
    assert "\n" in job.description


def test_non_salary_header_segment_yields_no_salary(monkeypatch):
    source = _source_with_comment(
        monkeypatch, "Acme | Engineer | Remote | Full-time<p>Great role."
    )

    job = source.fetch().jobs[0]

    assert job.salary_raw is None
    assert job.salary_type.value == "unknown"


def test_long_header_title_is_capped(monkeypatch):
    text = f"Acme | {'Engineer ' * 60}| Remote"
    source = _source_with_comment(monkeypatch, text)

    job = source.fetch().jobs[0]

    assert len(job.title) <= 201
    assert job.title.endswith("…")


def test_funding_amount_is_not_salary(monkeypatch):
    """A raised amount in the body must not become salary_raw."""
    text = (
        "Clad | Software Engineer | NYC | withclad.com"
        "<p>We are a 7 person team. We raised $2.7M and have >3 years of runway."
    )
    source = _source_with_comment(monkeypatch, text)

    job = source.fetch().jobs[0]

    assert job.salary_raw is None


def test_savings_amount_is_not_salary(monkeypatch):
    text = (
        "ThreatMark | Security Engineer | REMOTE | Equity"
        "<p>We protect >60M users and save > $1.2M every day in losses."
    )
    source = _source_with_comment(monkeypatch, text)

    job = source.fetch().jobs[0]

    assert job.salary_raw is None


def test_revenue_example_is_not_salary(monkeypatch):
    text = (
        "Acme | Product Engineer | Remote"
        "<p>I shipped a widget that generated $10k+ in direct revenue."
    )
    source = _source_with_comment(monkeypatch, text)

    job = source.fetch().jobs[0]

    assert job.salary_raw is None


def test_body_salary_with_pay_cue_is_extracted(monkeypatch):
    text = "Acme | Backend Engineer | Remote<p>Compensation: $190k - $220k plus equity."
    source = _source_with_comment(monkeypatch, text)

    job = source.fetch().jobs[0]

    assert job.salary_raw == "$190k - $220k"


def test_body_range_is_extracted_without_cue(monkeypatch):
    """Explicit ranges are specific enough to trust in body prose."""
    text = "Acme | Engineer | Remote<p>Forward Deployed Engineer ($148K – $255K) — NYC"
    source = _source_with_comment(monkeypatch, text)

    job = source.fetch().jobs[0]

    assert job.salary_raw == "$148K – $255K"


def test_header_salary_beyond_fourth_pipe_field(monkeypatch):
    text = "Acme | Engineer | Remote | Full-time | $190k + equity"
    source = _source_with_comment(monkeypatch, text)

    job = source.fetch().jobs[0]

    assert job.salary_raw == "$190k"
