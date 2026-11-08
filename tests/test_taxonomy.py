"""Unit tests for the skills taxonomy."""

from src.ingestion.skills_taxonomy import (
    SOFT_SKILLS,
    TECHNICAL_SKILLS,
    extract_skills,
    get_skill_tier,
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
        assert "Recruiting" not in extract_skills("Recruiting experience required.")

    def test_hyphen_aliases_match(self):
        assert "Compliance" in extract_skills("PCI-DSS audits.")
        assert "Compliance" in extract_skills("PCI DSS audits.")
        assert "OpenAI" in extract_skills("GPT-4 and GPT-4o integration.")
        assert "System Design" in extract_skills("high-level design experience.")
        assert "AI Agents" in extract_skills("multi-agent systems.")
        assert "Client Communication" in extract_skills("client-facing role.")

    def test_hyphen_alias_boundaries_hold(self):
        assert "Compliance" not in extract_skills("pci-dss-extra nonsense")
        assert "OpenAI" not in extract_skills("xgpt-4o tooling")
        assert extract_skills("GPT-4 and GPT-4o integration").count("OpenAI") == 1

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


class TestRecruitingGate:
    def test_bare_prose_is_not_recruiting(self):
        assert "Recruiting" not in extract_skills(
            "You will support the recruiting process."
        )
        assert "Recruiting" not in extract_skills("Recruiting experience required.")

    def test_people_or_hr_title_allows_prose(self):
        for title in (
            "Technical Recruiter",
            "Recruiting Coordinator",
            "Talent Acquisition Partner",
            "People Operations Manager",
            "HR Business Partner",
        ):
            assert "Recruiting" in extract_skills(
                "You will own the recruiting process.", context=title
            )

    def test_non_hr_title_does_not_allow_prose(self):
        assert "Recruiting" not in extract_skills(
            "You will support the recruiting process.", context="Software Engineer"
        )

    def test_explicit_phrases_allow_recruiting(self):
        assert "Recruiting" in extract_skills(
            "Technical recruiting experience required."
        )
        assert "Recruiting" in extract_skills(
            "Partner with recruiters on the recruiting process."
        )
        assert "Recruiting" in extract_skills("Own talent acquisition end to end.")

    def test_tags_stay_authoritative(self):
        assert extract_skills("", extra_terms=["recruiting"]) == ["Recruiting"]

    def test_hiring_verb_is_still_ignored(self):
        assert "Recruiting" not in extract_skills(
            "We are hiring engineers.", context="Technical Recruiter"
        )


class TestGenericTermGate:
    def test_bare_generic_words_are_not_skills(self):
        assert "Monitoring" not in extract_skills(
            "This role involves monitoring production systems."
        )
        assert "Compliance" not in extract_skills(
            "You will ensure compliance with internal policies."
        )
        assert "Networking" not in extract_skills(
            "Networking opportunities with senior leaders."
        )
        assert "Accessibility" not in extract_skills(
            "Accessibility is important to our users."
        )

    def test_specific_aliases_award_generic_skills(self):
        assert "Monitoring" in extract_skills("Prometheus and Datadog experience.")
        assert "Monitoring" in extract_skills("observability tooling experience.")
        assert "Compliance" in extract_skills("Knowledge of GDPR and HIPAA rules.")
        assert "Compliance" in extract_skills("PCI-DSS audits.")
        assert "Compliance" in extract_skills("PCI DSS audits.")
        assert "Compliance" in extract_skills("ISO 27001 audits.")
        assert "Networking" in extract_skills("TCP/IP, VPC and load balancing experience.")
        assert "Accessibility" in extract_skills("WCAG and a11y auditing.")

    def test_bare_word_alongside_alias_is_counted_once(self):
        assert extract_skills("Monitoring and Prometheus tooling.").count("Monitoring") == 1

    def test_tags_stay_authoritative(self):
        expected = {
            "monitoring": "Monitoring",
            "compliance": "Compliance",
            "networking": "Networking",
            "accessibility": "Accessibility",
        }
        for tag, skill in expected.items():
            assert extract_skills("", extra_terms=[tag]) == [skill]

    def test_gate_does_not_suppress_neighbouring_skills(self):
        skills = extract_skills("Monitoring Python services.")
        assert "Monitoring" not in skills
        assert "Python" in skills


class TestTaxonomyStats:
    def test_stats(self):
        stats = get_taxonomy_stats()
        assert stats["total_skills"] > 100
        assert "categories" in stats

    def test_is_valid(self):
        assert is_valid_skill("Python")
        assert is_valid_skill("not-a-real-skill-xyz") is False


class TestSkillTiers:
    def test_default_tier_is_technical(self):
        assert get_skill_tier("Python") == "technical"
        assert get_skill_tier("Docker") == "technical"
        assert get_skill_tier("Agile") == "technical"

    def test_soft_skills_are_exactly_the_curated_set(self):
        assert SOFT_SKILLS == {
            "Team Leadership",
            "Mentoring",
            "Strategic Planning",
            "Cross-functional Collaboration",
            "Recruiting",
            "Performance Management",
            "Communication",
            "Technical Writing",
            "Public Speaking",
            "Interpersonal Skills",
            "Client Communication",
            "Negotiation",
            "Presentation",
            "English",
            "German",
        }

    def test_tiers_are_disjoint_and_cover_the_taxonomy(self):
        stats = get_taxonomy_stats()
        assert SOFT_SKILLS.isdisjoint(TECHNICAL_SKILLS)
        assert len(SOFT_SKILLS) + len(TECHNICAL_SKILLS) == stats["total_skills"]

    def test_generic_technical_skills_are_not_soft(self):
        for skill in ("Monitoring", "Compliance", "Networking", "Accessibility"):
            assert skill in TECHNICAL_SKILLS

    def test_alias_resolves_to_tier(self):
        assert get_skill_tier("golang") == "technical"
        assert get_skill_tier("mentorship") == "soft"
        assert get_skill_tier("recruiting") == "soft"
        assert get_skill_tier("Unicorn Whispering") is None

    def test_stats_report_tiers(self):
        stats = get_taxonomy_stats()
        assert stats["tiers"] == {
            "technical": len(TECHNICAL_SKILLS),
            "soft": len(SOFT_SKILLS),
        }