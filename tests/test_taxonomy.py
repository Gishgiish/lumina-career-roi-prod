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

    def test_hiring_verb_is_not_a_skill(self):
        assert normalize_skill("hiring") is None
        assert normalize_skill("recruiting") == "Recruiting"
        assert normalize_skill("talent acquisition") == "Recruiting"

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

    def test_ambiguous_go_requires_language_context(self):
        assert "Go" not in extract_skills("We go to market with our product.")
        assert "Go" in extract_skills("Go developer needed.")
        assert "Go" in extract_skills("golang experience required.")

    def test_ambiguous_go_from_tag(self):
        assert "Go" in extract_skills("We go to market.", extra_terms=["go"])

    def test_ambiguous_c_requires_language_context(self):
        assert "C" not in extract_skills("Section C of the form.")
        assert "C" not in extract_skills("Experience selling to C-suite buyers.")
        assert "C" in extract_skills("C/C++ developer.")
        assert "C" in extract_skills("Experience with Go, C, or Python.")

    def test_ambiguous_r_requires_language_context(self):
        assert "R" not in extract_skills("Generate R$455.500 in revenue.")
        assert "R" in extract_skills("R language experience required.")

    def test_hiring_verb_is_not_extracted(self):
        assert "Recruiting" not in extract_skills("We are hiring engineers.")
        assert "Recruiting" in extract_skills("Recruiting experience required.")

    def test_tag_casing_is_normalized(self):
        assert extract_skills("", extra_terms=["Python", "React"]) == ["Python", "React"]

    def test_slash_aliases_match(self):
        assert "CI/CD" in extract_skills("We run CI/CD pipelines.")
        assert "A/B Testing" in extract_skills("A/B Testing experience.")
        assert "UI/UX Design" in extract_skills("", extra_terms=["UI/UX"])

    def test_markup_attributes_do_not_become_skills(self):
        markup = "&lt;div class=&quot;c-link&quot;&gt;Python&lt;/div&gt;"
        skills = extract_skills(markup)
        assert "C" not in skills
        assert "Python" in skills

    def test_ambiguous_gate_ignores_prose_next_to_other_languages(self):
        assert "Go" not in extract_skills("We go to market and build in Python.")
        assert "C" not in extract_skills("Section C of the form, and Python is used.")
        assert "R" not in extract_skills("R&D team using Python.")
        assert "Go" not in extract_skills("We go. Python is used elsewhere.")

    def test_ambiguous_gate_keeps_language_lists(self):
        assert "Go" in extract_skills("We use Ruby on Rails, Python, and Go for services.")
        assert "Go" in extract_skills("Ruby on Rails and Go lang.")
        assert "R" in extract_skills("Vaardigheid in Python en/of R voor analyses.")


class TestTaxonomyStats:
    def test_stats(self):
        stats = get_taxonomy_stats()
        assert stats["total_skills"] > 100
        assert "categories" in stats

    def test_is_valid(self):
        assert is_valid_skill("Python")
        assert is_valid_skill("not-a-real-skill-xyz") is False