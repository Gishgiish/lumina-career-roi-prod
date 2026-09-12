"""Unit tests for the skills taxonomy."""

from src.ingestion.skills_taxonomy import (
    extract_skills,
    get_taxonomy_stats,
    is_valid_skill,
    normalize_skill,
)


class TestNormalizeSkill:
    def test_exact_match(self):
        assert normalize_skill("Python") == "Python"
        assert normalize_skill("python") == "Python"
        assert normalize_skill("AWS") == "AWS"
        assert normalize_skill("Kubernetes") == "Kubernetes"

    def test_alias_match(self):
        assert normalize_skill("golang") == "Go"
        assert normalize_skill("node.js") == "JavaScript"
        assert normalize_skill("reactjs") == "React"
        assert normalize_skill("pyspark") == "Apache Spark"

    def test_paren_removal(self):
        assert normalize_skill("Python (2+ years)") == "Python"

    def test_unknown_returns_none(self):
        assert normalize_skill("Unicorn Whispering") is None

    def test_empty(self):
        assert normalize_skill("") is None
        assert normalize_skill(None) is None


class TestExtractSkills:
    def test_extract_from_description(self):
        text = "We are looking for a Python developer with Docker and AWS experience."
        skills = extract_skills(text)
        assert "Python" in skills
        assert "Docker" in skills
        assert "AWS" in skills

    def test_extract_with_extra_terms(self):
        skills = extract_skills("", extra_terms=["python", "react"])
        assert "Python" in skills
        assert "React" in skills

    def test_empty_text(self):
        assert extract_skills("") == []
        assert extract_skills(None) == []

    def test_deduplicates(self):
        text = "Python and python and PYTHON"
        skills = extract_skills(text)
        assert len([s for s in skills if s == "Python"]) == 1


class TestTaxonomyStats:
    def test_stats(self):
        stats = get_taxonomy_stats()
        assert stats["total_skills"] > 100
        assert "categories" in stats

    def test_is_valid(self):
        assert is_valid_skill("Python")
        assert is_valid_skill("not-a-real-skill-xyz") is False