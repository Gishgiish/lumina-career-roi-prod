# src/ingestion/skills_taxonomy.py
"""
Comprehensive skills taxonomy for Lumina Career ROI.

Maps various skill names/aliases to canonical skill names, organized by
category. This is used to extract skills from job postings, normalize
skills from different sources, and power the ROI marts.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Skill:
    canonical: str
    category: str
    aliases: tuple[str, ...] = field(default_factory=tuple)

# Curated taxonomy of technical and professional skills.
SKILLS: list[Skill] = [
    # ========== Programming Languages ==========
    Skill("Python", "Programming Languages", ("py", "python3")),
    Skill("JavaScript", "Programming Languages", ("js", "node.js", "nodejs", "ecmascript")),
    Skill("TypeScript", "Programming Languages", ("ts",)),
    Skill("Java", "Programming Languages", ("core java",)),
    Skill("C#", "Programming Languages", ("csharp", ".net", "dotnet")),
    Skill("C++", "Programming Languages", ("cpp",)),
    Skill("C", "Programming Languages", ()),
    Skill("Go", "Programming Languages", ("golang",)),
    Skill("Rust", "Programming Languages", ()),
    Skill("Ruby", "Programming Languages", ()),
    Skill("PHP", "Programming Languages", ()),
    Skill("Swift", "Programming Languages", ()),
    Skill("Kotlin", "Programming Languages", ()),
    Skill("Scala", "Programming Languages", ()),
    Skill("R", "Programming Languages", ("r language",)),
    Skill("SQL", "Programming Languages", ("structured query language",)),
    Skill("Bash", "Programming Languages", ("shell scripting", "bash scripting")),
    Skill("PowerShell", "Programming Languages", ("ps1",)),
    Skill("Perl", "Programming Languages", ()),
    Skill("Dart", "Programming Languages", ()),
    Skill("Elixir", "Programming Languages", ()),
    Skill("Haskell", "Programming Languages", ()),
    Skill("Lua", "Programming Languages", ()),
    Skill("Julia", "Programming Languages", ()),
    Skill("MATLAB", "Programming Languages", ()),
    Skill("COBOL", "Programming Languages", ()),
    Skill("Fortran", "Programming Languages", ()),
    Skill("F#", "Programming Languages", ("fsharp",)),
    Skill("Groovy", "Programming Languages", ()),
    Skill("Visual Basic", "Programming Languages", ("vba",)),
    Skill("ABAP", "Programming Languages", ("sap abap",)),
    Skill("Delphi", "Programming Languages", ("object pascal",)),
    Skill("Objective-C", "Programming Languages", ()),
    Skill("Assembly", "Programming Languages", ("asm",)),

    # ========== Web Development ==========
    Skill("HTML", "Web Development", ("html5",)),
    Skill("CSS", "Web Development", ("css3", "sass", "scss", "less")),
    Skill("React", "Web Development", ("react.js", "reactjs", "next.js", "nextjs")),
    Skill("Vue.js", "Web Development", ("vue", "nuxt", "nuxt.js")),
    Skill("Angular", "Web Development", ("angularjs", "angular 2")),
    Skill("Svelte", "Web Development", ("sveltekit",)),
    Skill("jQuery", "Web Development", ()),
    Skill("Bootstrap", "Web Development", ()),
    Skill("Tailwind CSS", "Web Development", ("tailwind", "tailwindcss")),
    Skill("Redux", "Web Development", ("redux toolkit",)),
    Skill("MobX", "Web Development", ()),
    Skill("Zustand", "Web Development", ()),
    Skill("GraphQL", "Web Development", ("apollo", "hasura")),
    Skill("REST APIs", "Web Development", ("restful", "rest api")),
    Skill("gRPC", "Web Development", ()),
    Skill("WebSockets", "Web Development", ("socket.io",)),
    Skill("WebAssembly", "Web Development", ("wasm",)),
    Skill("Progressive Web Apps", "Web Development", ("pwa",)),
    Skill("Django", "Web Development", ("django rest framework",)),
    Skill("Flask", "Web Development", ()),
    Skill("FastAPI", "Web Development", ()),
    Skill("Express.js", "Web Development", ("express", "expressjs")),
    Skill("NestJS", "Web Development", ("nest.js",)),
    Skill("Ruby on Rails", "Web Development", ("rails",)),
    Skill("Laravel", "Web Development", ()),
    Skill("Spring Boot", "Web Development", ("spring", "spring framework")),
    Skill("ASP.NET", "Web Development", (".net core", ".net 6", ".net 7", ".net 8")),
    Skill("Symfony", "Web Development", ()),
    Skill("WordPress", "Web Development", ("wp",)),
    Skill("Drupal", "Web Development", ()),
    Skill("Shopify", "Web Development", ()),
    Skill("Magento", "Web Development", ()),
    Skill("Microservices", "Web Development", ("micro service",)),
    Skill("Serverless", "Web Development", ("lambda serverless",)),
    Skill("OpenAPI", "Web Development", ("swagger",)),
    Skill("Jest", "Web Development", ()),
    Skill("Playwright", "Web Development", ()),
    Skill("Cypress", "Web Development", ()),
    Skill("Webpack", "Web Development", ("vite", "rollup", "esbuild")),
    Skill("NPM", "Web Development", ("yarn", "pnpm", "bun")),
    Skill("Remix", "Web Development", ("remix.run",)),
    Skill("Astro", "Web Development", ()),
    Skill("Gatsby", "Web Development", ()),
    Skill("HTMX", "Web Development", ()),
    Skill("Solid.js", "Web Development", ("solidjs",)),
    Skill("Selenium", "Web Development", ()),

    # ========== Data & Analytics ==========
    Skill("Pandas", "Data & Analytics", ()),
    Skill("NumPy", "Data & Analytics", ()),
    Skill("Polars", "Data & Analytics", ()),
    Skill("Apache Spark", "Data & Analytics", ("pyspark", "spark sql", "spark")),
    Skill("Hadoop", "Data & Analytics", ()),
    Skill("DuckDB", "Data & Analytics", ()),
    Skill("Apache Flink", "Data & Analytics", ("flink",)),
    Skill("Apache Kafka", "Data & Analytics", ("kafka", "kafka streams")),
    Skill("Apache Airflow", "Data & Analytics", ("airflow",)),
    Skill("Prefect", "Data & Analytics", ()),
    Skill("dbt", "Data & Analytics", ("data build tool",)),
    Skill("Trino", "Data & Analytics", ("presto",)),
    Skill("Snowflake", "Data & Analytics", ()),
    Skill("Databricks", "Data & Analytics", ()),
    Skill("BigQuery", "Data & Analytics", ("google bigquery",)),
    Skill("Redshift", "Data & Analytics", ("amazon redshift",)),
    Skill("ClickHouse", "Data & Analytics", ()),
    Skill("Tableau", "Data & Analytics", ()),
    Skill("Power BI", "Data & Analytics", ("powerbi",)),
    Skill("Looker", "Data & Analytics", ("looker studio",)),
    Skill("Metabase", "Data & Analytics", ()),
    Skill("Grafana", "Data & Analytics", ()),
    Skill("Apache Superset", "Data & Analytics", ("superset",)),
    Skill("Excel", "Data & Analytics", ("microsoft excel", "google sheets")),
    Skill("ETL", "Data & Analytics", ("extract transform load", "data pipelines")),
    Skill("Data Warehousing", "Data & Analytics", ("data warehouse",)),
    Skill("Data Modeling", "Data & Analytics", ("dimensional modeling",)),
    Skill("Data Lake", "Data & Analytics", ("data lakes",)),
    Skill("Data Governance", "Data & Analytics", ("data lineage", "data catalog")),
    Skill("Business Intelligence", "Data & Analytics", ("bi tools", "bi reporting")),
    Skill("Statistics", "Data & Analytics", ("statistical analysis",)),
    Skill("A/B Testing", "Data & Analytics", ("experimentation",)),
    Skill("Data Visualization", "Data & Analytics", ("data viz", "d3.js", "d3")),

    # ========== Machine Learning & AI ==========
    Skill("Machine Learning", "Machine Learning & AI", ("ml",)),
    Skill("Deep Learning", "Machine Learning & AI", ("dl",)),
    Skill("PyTorch", "Machine Learning & AI", ()),
    Skill("TensorFlow", "Machine Learning & AI", ("keras",)),
    Skill("Scikit-learn", "Machine Learning & AI", ("sklearn",)),
    Skill("XGBoost", "Machine Learning & AI", ()),
    Skill("LangChain", "Machine Learning & AI", ()),
    Skill("LlamaIndex", "Machine Learning & AI", ()),
    Skill("OpenAI", "Machine Learning & AI", ("chatgpt", "gpt-4", "gpt-4o")),
    Skill("Hugging Face", "Machine Learning & AI", ("huggingface", "transformers")),
    Skill("RAG", "Machine Learning & AI", ("retrieval augmented generation", "embeddings")),
    Skill("Natural Language Processing", "Machine Learning & AI", ("nlp", "text mining")),
    Skill("Computer Vision", "Machine Learning & AI", ("object detection", "image recognition")),
    Skill("Large Language Models", "Machine Learning & AI", ("llm", "llms")),
    Skill("Fine-tuning", "Machine Learning & AI", ("finetuning",)),
    Skill("Prompt Engineering", "Machine Learning & AI", ("prompting",)),
    Skill("MLOps", "Machine Learning & AI", ("ml ops",)),
    Skill("MLflow", "Machine Learning & AI", ()),
    Skill("Reinforcement Learning", "Machine Learning & AI", ("rl",)),
    Skill("Recommendation Systems", "Machine Learning & AI", ("recommender systems",)),
    Skill("Time Series Analysis", "Machine Learning & AI", ("forecasting",)),
    Skill("Anomaly Detection", "Machine Learning & AI", ()),
    Skill("Model Deployment", "Machine Learning & AI", ("model serving",)),
    Skill("AI Agents", "Machine Learning & AI", ("agentic ai", "multi-agent")),
    Skill("CrewAI", "Machine Learning & AI", ()),
    Skill("Stable Diffusion", "Machine Learning & AI", ()),
    Skill("Ollama", "Machine Learning & AI", ()),

    # ========== Cloud & DevOps ==========
    Skill("AWS", "Cloud & DevOps", ("amazon web services", "aws cloud")),
    Skill("Azure", "Cloud & DevOps", ("microsoft azure",)),
    Skill("Google Cloud", "Cloud & DevOps", ("gcp", "google cloud platform")),
    Skill("Docker", "Cloud & DevOps", ("docker compose", "containerization")),
    Skill("Kubernetes", "Cloud & DevOps", ("k8s", "gke", "eks", "aks")),
    Skill("Terraform", "Cloud & DevOps", ("iac", "infrastructure as code")),
    Skill("Ansible", "Cloud & DevOps", ()),
    Skill("Pulumi", "Cloud & DevOps", ()),
    Skill("CloudFormation", "Cloud & DevOps", ("aws cloudformation",)),
    Skill("CI/CD", "Cloud & DevOps", ("continuous integration", "continuous deployment")),
    Skill("GitHub Actions", "Cloud & DevOps", ()),
    Skill("GitLab CI", "Cloud & DevOps", ("gitlab ci/cd",)),
    Skill("Jenkins", "Cloud & DevOps", ()),
    Skill("CircleCI", "Cloud & DevOps", ()),
    Skill("ArgoCD", "Cloud & DevOps", ("argo cd", "gitops")),
    Skill("Helm", "Cloud & DevOps", ("helm charts",)),
    Skill("Linux", "Cloud & DevOps", ("linux administration", "unix")),
    Skill("Networking", "Cloud & DevOps", ("tcp/ip", "load balancing", "vpc")),
    Skill("Monitoring", "Cloud & DevOps", ("observability", "prometheus", "datadog")),
    Skill("ELK Stack", "Cloud & DevOps", ("elasticsearch", "logstash", "kibana", "elastic stack")),
    Skill("Splunk", "Cloud & DevOps", ()),
    Skill("SRE", "Cloud & DevOps", ("site reliability engineering",)),
    Skill("DevOps", "Cloud & DevOps", ("devops practices",)),
    Skill("Nginx", "Cloud & DevOps", ()),
    Skill("Vault", "Cloud & DevOps", ("hashicorp vault",)),
    Skill("Istio", "Cloud & DevOps", ("service mesh",)),
    Skill("Cloudflare", "Cloud & DevOps", ("cloudflare workers",)),
    Skill("Heroku", "Cloud & DevOps", ()),
    Skill("Vercel", "Cloud & DevOps", ()),
    Skill("Netlify", "Cloud & DevOps", ()),
    Skill("Firebase", "Cloud & DevOps", ()),
    Skill("Supabase", "Cloud & DevOps", ()),
    Skill("Vagrant", "Cloud & DevOps", ()),

    # ========== Databases ==========
    Skill("PostgreSQL", "Databases", ("postgres", "psql")),
    Skill("MySQL", "Databases", ()),
    Skill("SQLite", "Databases", ()),
    Skill("MongoDB", "Databases", ("mongodb atlas",)),
    Skill("Redis", "Databases", ("redis cache",)),
    Skill("Cassandra", "Databases", ("apache cassandra",)),
    Skill("DynamoDB", "Databases", ("amazon dynamodb",)),
    Skill("Elasticsearch", "Databases", ("elastic search", "opensearch")),
    Skill("Neo4j", "Databases", ("graph database",)),
    Skill("MSSQL", "Databases", ("sql server", "microsoft sql server")),
    Skill("Oracle", "Databases", ("oracle database", "oracle sql")),
    Skill("MariaDB", "Databases", ()),
    Skill("Couchbase", "Databases", ()),
    Skill("InfluxDB", "Databases", ("time series database",)),
    Skill("Pinecone", "Databases", ("vector database", "chroma", "weaviate", "qdrant")),
    Skill("Database Design", "Databases", ("schema design",)),
    Skill("Database Administration", "Databases", ("dba",)),
    Skill("Query Optimization", "Databases", ("sql optimization", "query tuning")),
    Skill("Firestore", "Databases", ("cloud firestore",)),

    # ========== Mobile Development ==========
    Skill("Android Development", "Mobile Development", ("android", "android sdk")),
    Skill("iOS Development", "Mobile Development", ("ios", "ios sdk", "xcode")),
    Skill("React Native", "Mobile Development", ()),
    Skill("Flutter", "Mobile Development", ()),
    Skill("SwiftUI", "Mobile Development", ()),
    Skill("Jetpack Compose", "Mobile Development", ()),
    Skill("Xamarin", "Mobile Development", ()),
    Skill("Ionic", "Mobile Development", ()),
    Skill("Expo", "Mobile Development", ()),
    Skill("Unity", "Mobile Development", ()),
    Skill("Unreal Engine", "Mobile Development", ("unreal", "ue5")),
    Skill("AR/VR Development", "Mobile Development", ("augmented reality", "virtual reality")),

    # ========== Security ==========
    Skill("Cybersecurity", "Security", ("cyber security", "information security", "infosec")),
    Skill("Network Security", "Security", ("network defense", "firewall")),
    Skill("Application Security", "Security", ("appsec",)),
    Skill("Cloud Security", "Security", ("aws security", "cloudsec")),
    Skill("DevSecOps", "Security", ()),
    Skill("Identity and Access Management", "Security", ("iam", "access control", "sso")),
    Skill("Encryption", "Security", ("cryptography", "tls", "ssl")),
    Skill("Security Operations", "Security", ("soc", "incident response", "threat hunting")),
    Skill("Ethical Hacking", "Security", ("penetration testing", "pen testing")),
    Skill("SIEM", "Security", ("splunk siem",)),
    Skill("Compliance", "Security", ("gdpr", "hipaa", "pci-dss", "iso 27001")),
    Skill("Risk Management", "Security", ("threat modeling", "security audit")),
    Skill("Zero Trust", "Security", ("zero trust architecture",)),

    # ========== Project Management & Leadership ==========
    Skill("Agile", "Project Management", ("scrum", "kanban", "sprint")),
    Skill("Scrum", "Project Management", ("scrum master",)),
    Skill("Kanban", "Project Management", ()),
    Skill("Waterfall", "Project Management", ()),
    Skill("Project Management", "Project Management", ("project planning",)),
    Skill("Product Management", "Project Management", ("product owner",)),
    Skill("Stakeholder Management", "Project Management", ()),
    Skill("JIRA", "Project Management", ("jira administration",)),
    Skill("Confluence", "Project Management", ()),
    Skill("Asana", "Project Management", ()),
    Skill("Trello", "Project Management", ()),
    Skill("Roadmapping", "Project Management", ("product roadmap",)),
    Skill("Budget Management", "Project Management", ("budgeting",)),
    Skill("Vendor Management", "Project Management", ()),
    Skill("OKRs", "Project Management", ("objectives and key results",)),
    Skill("KPI Tracking", "Project Management", ("key performance indicators",)),
    Skill("Technical Leadership", "Leadership", ("tech lead", "engineering leadership")),
    Skill("Team Leadership", "Leadership", ("team lead", "people management")),
    Skill("Mentoring", "Leadership", ("mentorship", "coaching")),
    Skill("Strategic Planning", "Leadership", ("strategy",)),
    Skill("Cross-functional Collaboration", "Leadership", ("cross functional",)),
    Skill("Hiring", "Leadership", ("recruiting", "talent acquisition")),
    Skill("Performance Management", "Leadership", ("performance reviews",)),

    # ========== Communication & Soft Skills ==========
    Skill("Communication", "Communication", ("communication skills",)),
    Skill("Technical Writing", "Communication", ("documentation", "api documentation")),
    Skill("Public Speaking", "Communication", ("presentation skills",)),
    Skill("Interpersonal Skills", "Communication", ("soft skills",)),
    Skill("Client Communication", "Communication", ("client-facing",)),
    Skill("Negotiation", "Communication", ()),
    Skill("Presentation", "Communication", ("slide decks", "powerpoint")),
    Skill("English", "Communication", ("fluent english",)),
    Skill("German", "Communication", ("german language",)),

    # ========== Design & UX ==========
    Skill("UI/UX Design", "Design & UX", ("user experience", "user interface", "ux design", "ui design")),
    Skill("Figma", "Design & UX", ()),
    Skill("Adobe XD", "Design & UX", ()),
    Skill("Sketch", "Design & UX", ()),
    Skill("User Research", "Design & UX", ("user testing", "usability testing")),
    Skill("Wireframing", "Design & UX", ("wireframes",)),
    Skill("Prototyping", "Design & UX", ()),
    Skill("Design Systems", "Design & UX", ()),
    Skill("Accessibility", "Design & UX", ("a11y", "wcag")),
    Skill("Responsive Design", "Design & UX", ("mobile first",)),
    Skill("Interaction Design", "Design & UX", ("ixd",)),
    Skill("Design Thinking", "Design & UX", ()),
    Skill("Adobe Creative Suite", "Design & UX", ("photoshop", "illustrator")),
    Skill("Branding", "Design & UX", ("brand identity",)),
    Skill("User Flows", "Design & UX", ()),

    # ========== Other Technical ==========
    Skill("Git", "Other Technical", ("github", "gitlab", "bitbucket", "version control")),
    Skill("Caching", "Other Technical", ("cache", "cdn")),
    Skill("API Design", "Other Technical", ("api development",)),
    Skill("Algorithm Design", "Other Technical", ("algorithms", "data structures")),
    Skill("Object-Oriented Programming", "Other Technical", ("oop",)),
    Skill("Functional Programming", "Other Technical", ("fp",)),
    Skill("System Design", "Other Technical", ("distributed systems", "high-level design")),
    Skill("Code Review", "Other Technical", ("peer review",)),
    Skill("Refactoring", "Other Technical", ("legacy code",)),
    Skill("Debugging", "Other Technical", ("troubleshooting",)),
    Skill("Performance Optimization", "Other Technical", ("performance tuning",)),
    Skill("Embedded Systems", "Other Technical", ("firmware", "microcontrollers")),
    Skill("IoT", "Other Technical", ("internet of things",)),
    Skill("Salesforce", "Other Technical", ("crm",)),
    Skill("SAP", "Other Technical", ("sap s/4hana",)),
    Skill("Blue Prism", "Other Technical", ("rpa", "uipath")),
    Skill("ServiceNow", "Other Technical", ()),
    Skill("Workday", "Other Technical", ()),
    Skill("SharePoint", "Other Technical", ()),
    Skill("Slack", "Other Technical", ()),
    Skill("Notion", "Other Technical", ()),
]

# Build a lookup dictionary: lowercase alias -> canonical Skill
_ALIAS_LOOKUP: dict[str, Skill] = {}
for skill in SKILLS:
    _ALIAS_LOOKUP[skill.canonical.lower()] = skill
    for alias in skill.aliases:
        _ALIAS_LOOKUP[alias.strip().lower()] = skill

# Also index by category for convenience
SKILLS_BY_CATEGORY: dict[str, list[Skill]] = {}
for skill in SKILLS:
    SKILLS_BY_CATEGORY.setdefault(skill.category, []).append(skill)


def normalize_skill(name: str) -> str | None:
    """
    Takes a raw skill name (from a source's tags, or extracted from text)
    and returns the canonical skill name, or None if not recognized.
    """
    if not name:
        return None
    candidate = name.strip().lower()
    # Direct lookup
    if candidate in _ALIAS_LOOKUP:
        return _ALIAS_LOOKUP[candidate].canonical
    # Try removing parenthetical qualifiers like "(2+ years)"
    import re
    candidate_clean = re.sub(r"[\(\[].*?[\)\]]", "", candidate).strip()
    if candidate_clean in _ALIAS_LOOKUP:
        return _ALIAS_LOOKUP[candidate_clean].canonical
    return None


def extract_skills(text: str, extra_terms: list[str] | None = None) -> list[str]:
    """
    Extract canonical skill names from arbitrary text (job descriptions,
    source tags, etc.).

    Matching strategy:
      1. Tokenize the text on word boundaries.
      2. For each token and multi-word phrase up to 3 words, check the alias table.
      3. Return deduplicated, canonical skill names.

    This is a simple but effective keyword-based extractor. For a more
    sophisticated approach in the future, this could be swapped with a
    spaCy NER pipeline or skillNer.
    """
    import re

    if not text and not extra_terms:
        return []

    # Add explicit tags to the search surface
    search_text = (text or "").lower()
    if extra_terms:
        search_text += " " + " ".join(extra_terms)

    found: list[str] = []

    # Collect all unique candidate tokens and n-grams (up to 3 words)
    tokens = re.findall(r"[a-z0-9.#+]+", search_text)
    candidates: set[str] = set()
    for i in range(len(tokens)):
        # 1-gram
        candidates.add(tokens[i])
        # 2-gram
        if i + 1 < len(tokens):
            candidates.add(f"{tokens[i]} {tokens[i+1]}")
        # 3-gram
        if i + 2 < len(tokens):
            candidates.add(f"{tokens[i]} {tokens[i+1]} {tokens[i+2]}")

    # Look up each candidate (and alias) in the taxonomy
    seen: set[str] = set()
    for candidate in candidates:
        canonical = normalize_skill(candidate)
        if canonical and canonical.lower() not in seen:
            seen.add(canonical.lower())
            found.append(canonical)

    # Sort for stable output
    found.sort()
    return found


def get_taxonomy_stats() -> dict:
    """Simple stats about the taxonomy for debugging/admin."""
    return {
        "total_skills": len(SKILLS),
        "total_aliases": sum(len(s.aliases) for s in SKILLS),
        "categories": {cat: len(items) for cat, items in SKILLS_BY_CATEGORY.items()},
    }


def is_valid_skill(name: str) -> bool:
    """Checks if a name is a known skill in the taxonomy."""
    return normalize_skill(name) is not None