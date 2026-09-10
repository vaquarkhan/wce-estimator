#!/usr/bin/env python3
"""
Author: Viquar Khan (ORCID 0009-0008-3592-4162).

Prior libraries for the WCE Estimator.

All multiplier bands (a_low, a_mode, a_high) are AI *effort multipliers*:
    a < 1  -> AI makes the work faster
    a = 1  -> no change
    a > 1  -> AI makes the work slower (documented for experienced developers on
              mature code; METR 2025, arXiv:2507.09089)

Bands are anchored to the same empirical spread used in the paper's reproducible
model (estimation_framework.py / wce_estimate.py):
    greenfield codegen    ~0.44 time factor  (Peng et al. 2023, 55.8% faster)
    enterprise mixed task ~0.75-0.80         (Cui et al. 2024; RCT arXiv:2410.12944)
    legacy / mature repo  ~1.0-1.2 (slower)  (METR 2025, +19% time)
    review / rework       >1.0 (more churn)  (GitClear 2024/25; DORA 2024)

This module is the single source of truth for how a work item with only a
work-class label or an AI-difficulty tier gets a multiplier band.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# AI-difficulty tiers (paper Table 6). "AI-difficulty" is how resistant the work
# is to AI acceleration -- NOT functional/business complexity. A gnarly business
# rule that is still just code generation can be LOW AI-difficulty; a trivial-
# looking change deep in a legacy monolith can be HIGH.
# ---------------------------------------------------------------------------
# Values are taken directly from the paper's Table 6 "Typical a_i" ranges:
#   Low 0.45-0.65, Medium 0.70-0.90, High 0.95-1.25. The mode is the midpoint of
# each stated range; low/high are the stated range bounds (used for the triangular
# Monte Carlo draw). These are the paper's numbers, not a widened synthesis.
DIFFICULTY_BANDS = {
    # tier    : (a_low, a_mode, a_high)   -> matches paper Table 6 ranges exactly
    "low":    (0.45, 0.55, 0.65),   # AI accelerates strongly (Table 6: 0.45-0.65)
    "medium": (0.70, 0.80, 0.90),   # AI helps with oversight  (Table 6: 0.70-0.90)
    "high":   (0.95, 1.10, 1.25),   # AI neutral or slower      (Table 6: 0.95-1.25)
}

# Human-friendly aliases accepted from the spreadsheet's "AI Difficulty" column.
DIFFICULTY_ALIASES = {
    "low": "low", "l": "low", "easy": "low", "simple": "low", "green": "low",
    "greenfield": "low", "1": "low",
    "medium": "medium", "med": "medium", "m": "medium", "moderate": "medium",
    "mixed": "medium", "2": "medium",
    "high": "high", "h": "high", "hard": "high", "complex": "high",
    "legacy": "high", "difficult": "high", "3": "high",
}

# ---------------------------------------------------------------------------
# Work-class default priors. Keyed by canonical class name; matched against the
# spreadsheet "Work Class" column via substring keywords (see KEYWORDS below).
#   (a_low, a_mode, a_high, essential)
# "essential" marks work AI structurally cannot drive toward zero -- it sets the
# Khan Ceiling S_max = 1/phi (Proposition 1).
# ---------------------------------------------------------------------------
# The eight canonical classes reproduce the paper's Table 3 / estimation_framework.py
# PROFILE_PRODUCT bands exactly. The finer classes below them map named work items to
# the exact per-item bands used in the paper's Appendix C (wce_estimate.py). Two
# classes marked EXTENSION are not in the paper's taxonomy and are conservative
# additions for real projects (documentation) or aliases of legacy integration.
WORK_CLASS_PRIORS = {
    # --- Table 3 canonical eight (match PROFILE_PRODUCT exactly) ---
    "requirements":   (0.85, 0.95, 1.05, True),
    "architecture":   (0.85, 0.95, 1.05, True),
    "coordination":   (0.95, 1.00, 1.05, True),
    "net_new_code":   (0.40, 0.55, 0.80, False),
    "integration":    (0.90, 1.10, 1.35, False),
    "testing":        (0.60, 0.80, 1.05, False),
    "review_rework":  (0.95, 1.15, 1.45, False),
    "deployment":     (0.75, 0.90, 1.10, False),
    # --- Appendix C per-item bands (from wce_estimate.py) ---
    "api_backend":    (0.48, 0.60, 0.78, False),   # F2 REST API core
    "database":       (0.58, 0.70, 0.88, False),   # F3 PostgreSQL schema/data access
    "frontend_ui":    (0.58, 0.70, 0.90, False),   # F5/F6 complex React pages
    "simple_page":    (0.40, 0.52, 0.72, False),   # F8/F9 simple pages
    "security_auth":  (0.85, 0.95, 1.10, False),   # F1 auth + OTP
    "concurrency":    (0.90, 1.05, 1.25, False),   # F4 high-concurrency layer
    # --- compliance = essential regulated work (Table 3 essential family) ---
    "compliance":     (0.95, 1.05, 1.15, True),
    # --- EXTENSIONS beyond the paper's taxonomy, so the tool covers a full org
    #     SDLC. Multipliers follow the paper's logic: conceptual/coordination and
    #     human-driven validation resist AI (a near or above 1); code/artifact
    #     generation is accelerated (a < 1); ops/quality carry a rework tax. ---
    "data_migration":      (0.95, 1.10, 1.40, False),  # alias of legacy integration
    "documentation":       (0.45, 0.60, 0.80, False),  # generation-heavy, low AI-difficulty
    "ux_design":           (0.75, 0.88, 1.05, False),  # UX/UI design, wireframes, prototyping
    "cloud_infra":         (0.72, 0.88, 1.10, False),  # IaC/Terraform, provisioning, networking
    "observability":       (0.65, 0.80, 1.00, False),  # logging, metrics, alerting, dashboards
    "test_planning":       (0.70, 0.85, 1.00, False),  # test strategy & case design
    "test_automation":     (0.50, 0.65, 0.85, False),  # automated unit/integration/e2e tests
    "manual_testing":      (0.85, 0.95, 1.10, False),  # manual/exploratory/UAT (human-driven)
    "performance_testing": (0.85, 1.00, 1.20, False),  # load/stress/perf (correctness-critical)
    "support":             (0.85, 0.95, 1.10, False),  # production support & maintenance
    "ceremonies":          (0.98, 1.00, 1.05, True),   # agile ceremonies/meetings: non-accelerable
}

# Ordered keyword -> canonical class. First match wins and matching is anchored
# at a word start, so more specific keywords MUST precede generic ones.
KEYWORDS = [
    # --- agile ceremonies & meetings (non-accelerable coordination) ---
    ("sprint planning",  "ceremonies"),
    ("sprint review",    "ceremonies"),
    ("sprint",           "ceremonies"),
    ("standup",          "ceremonies"),
    ("stand-up",         "ceremonies"),
    ("scrum",            "ceremonies"),
    ("retrospective",    "ceremonies"),
    ("retro",            "ceremonies"),
    ("backlog refinement", "ceremonies"),
    ("refinement",       "ceremonies"),
    ("grooming",         "ceremonies"),
    ("pi planning",      "ceremonies"),
    ("ceremony",         "ceremonies"),
    ("ceremonies",       "ceremonies"),
    ("demo",             "ceremonies"),
    ("showcase",         "ceremonies"),
    ("agile",            "ceremonies"),
    # --- coordination / project management ---
    ("kickoff",          "coordination"),
    ("kick-off",         "coordination"),
    ("stakeholder",      "coordination"),
    ("coordination",     "coordination"),
    ("meeting",          "coordination"),
    ("alignment",        "coordination"),
    ("project management", "coordination"),
    ("test planning",    "test_planning"),   # before generic 'planning'
    ("release planning", "deployment"),
    ("capacity planning", "coordination"),
    ("planning",         "coordination"),
    # --- requirements / analysis (essential) ---
    ("requirement",      "requirements"),
    ("user story",       "requirements"),
    ("story mapping",    "requirements"),
    ("elicitation",      "requirements"),
    ("discovery",        "requirements"),
    # --- architecture & technical design incl. data modeling (essential) ---
    ("solution architecture", "architecture"),
    ("architecture",     "architecture"),
    ("data model",       "architecture"),
    ("data modelling",   "architecture"),
    ("erd",              "architecture"),
    ("entity relationship", "architecture"),
    ("schema design",    "architecture"),
    ("api design",       "architecture"),
    ("high-level design", "architecture"),
    ("low-level design", "architecture"),
    ("technical design", "architecture"),
    ("design decision",  "architecture"),
    # --- UX/UI design (accelerable) ---
    ("ux",               "ux_design"),
    ("ui design",        "ux_design"),
    ("user experience",  "ux_design"),
    ("wireframe",        "ux_design"),
    ("mockup",           "ux_design"),
    ("figma",            "ux_design"),
    ("prototype",        "ux_design"),
    ("design system",    "ux_design"),
    ("design",           "architecture"),   # generic 'design' -> architecture
    # --- compliance / regulatory / governance (essential) ---
    ("compliance",       "compliance"),
    ("regulatory",       "compliance"),
    ("audit",            "compliance"),
    ("sign-off",         "compliance"),
    ("governance",       "compliance"),
    # --- cloud & infrastructure (IaC, provisioning, networking) ---
    ("infrastructure as code", "cloud_infra"),
    ("terraform",        "cloud_infra"),
    ("cloudformation",   "cloud_infra"),
    ("iac",              "cloud_infra"),
    ("provision",        "cloud_infra"),
    ("kubernetes",       "cloud_infra"),
    ("k8s",              "cloud_infra"),
    ("helm",             "cloud_infra"),
    ("vpc",              "cloud_infra"),
    ("networking",       "cloud_infra"),
    ("cloud",            "cloud_infra"),
    # --- observability / monitoring ---
    ("observability",    "observability"),
    ("monitoring",       "observability"),
    ("logging",          "observability"),
    ("metrics",          "observability"),
    ("alerting",         "observability"),
    ("telemetry",        "observability"),
    ("grafana",          "observability"),
    ("prometheus",       "observability"),
    # --- CI/CD, deployment & release ---
    ("ci/cd",            "deployment"),
    ("cicd",             "deployment"),
    ("pipeline",         "deployment"),
    ("deployment",       "deployment"),
    ("deploy",           "deployment"),
    ("release",          "deployment"),
    ("devops",           "deployment"),
    ("cutover",          "deployment"),
    ("infra",            "deployment"),
    # --- security / auth ('authoring' guarded before 'auth') ---
    ("authoring",        "net_new_code"),
    ("security",         "security_auth"),
    ("authentication",   "security_auth"),
    ("authoriz",         "security_auth"),
    ("oauth",            "security_auth"),
    ("auth",             "security_auth"),
    ("otp",              "security_auth"),
    ("rbac",             "security_auth"),
    ("permission",       "security_auth"),
    ("encryption",       "security_auth"),
    # --- data: migration/ETL, then implementation ---
    ("data migration",   "data_migration"),
    ("migration",        "data_migration"),
    ("etl",              "data_migration"),
    ("database",         "database"),
    ("postgres",         "database"),
    ("schema",           "database"),
    ("sql",              "database"),
    ("data access",      "database"),
    ("stored procedure", "database"),
    ("orm",              "database"),
    ("query",            "database"),
    # --- API / backend ---
    ("rest",             "api_backend"),
    ("graphql",          "api_backend"),
    ("grpc",             "api_backend"),
    ("api",              "api_backend"),
    ("endpoint",         "api_backend"),
    ("backend",          "api_backend"),
    ("microservice",     "api_backend"),
    ("service",          "api_backend"),
    ("crud",             "api_backend"),
    ("notification",     "api_backend"),
    ("email",            "api_backend"),
    ("webhook",          "api_backend"),
    # --- concurrency / performance-critical build ---
    ("concurren",        "concurrency"),
    ("cache",            "concurrency"),
    ("scal",             "concurrency"),
    ("throughput",       "concurrency"),
    # --- frontend / UI ---
    ("simple page",      "simple_page"),
    ("static page",      "simple_page"),
    ("landing",          "simple_page"),
    ("react",            "frontend_ui"),
    ("angular",          "frontend_ui"),
    ("vue",              "frontend_ui"),
    ("frontend",         "frontend_ui"),
    ("front-end",        "frontend_ui"),
    ("dashboard",        "frontend_ui"),
    ("component",        "frontend_ui"),
    ("page",             "frontend_ui"),
    ("admin",            "frontend_ui"),
    ("ui",               "frontend_ui"),
    # --- integration ---
    ("integration",      "integration"),
    ("legacy",           "integration"),
    ("reverse-engineer", "integration"),
    ("reverse engineer", "integration"),
    ("third-party",      "integration"),
    ("3rd party",        "integration"),
    # --- testing (specific tiers before generic 'test') ---
    ("test plan",        "test_planning"),
    ("test strategy",    "test_planning"),
    ("test case design", "test_planning"),
    ("test design",      "test_planning"),
    ("test automation",  "test_automation"),
    ("automated test",   "test_automation"),
    ("unit test",        "test_automation"),
    ("integration test", "test_automation"),
    ("e2e",              "test_automation"),
    ("end-to-end test",  "test_automation"),
    ("end to end test",  "test_automation"),
    ("selenium",         "test_automation"),
    ("cypress",          "test_automation"),
    ("playwright",       "test_automation"),
    ("test suite",       "test_automation"),
    ("regression test",  "test_automation"),
    ("performance test", "performance_testing"),
    ("load test",        "performance_testing"),
    ("stress test",      "performance_testing"),
    ("soak test",        "performance_testing"),
    ("perf test",        "performance_testing"),
    ("manual test",      "manual_testing"),
    ("exploratory",      "manual_testing"),
    ("uat",              "manual_testing"),
    ("user acceptance",  "manual_testing"),
    ("manual validation", "manual_testing"),
    ("qa validation",    "manual_testing"),
    ("acceptance test",  "manual_testing"),
    ("test",             "testing"),
    ("qa",               "testing"),
    ("validation",       "testing"),
    ("debug",            "testing"),
    # --- review / rework / defects ---
    ("code review",      "review_rework"),
    ("review",           "review_rework"),
    ("rework",           "review_rework"),
    ("refactor",         "review_rework"),
    ("bug",              "review_rework"),
    ("defect",           "review_rework"),
    ("hotfix",           "review_rework"),
    # --- documentation ---
    ("documentation",    "documentation"),
    ("document",         "documentation"),
    ("docs",             "documentation"),
    ("runbook",          "documentation"),
    # --- production support / maintenance ---
    ("production support", "support"),
    ("on-call",          "support"),
    ("oncall",           "support"),
    ("maintenance",      "support"),
    ("support",          "support"),
    # --- generic net-new code fallbacks ---
    ("net-new",          "net_new_code"),
    ("net new",          "net_new_code"),
    ("feature",          "net_new_code"),
    ("greenfield",       "net_new_code"),
    ("implement",        "net_new_code"),
    ("development",      "net_new_code"),
]

# Keywords that force essential=True regardless of the class default, used when a
# class is ambiguous but the label clearly names essential (non-accelerable) work.
ESSENTIAL_KEYWORDS = (
    "requirement", "architecture", "design", "coordination", "stakeholder",
    "compliance", "audit", "sign-off", "regulatory", "discovery", "planning",
    "data model", "sprint", "standup", "scrum", "retrospective", "refinement",
    "ceremony", "ceremonies", "agile", "governance",
)

DEFAULT_CLASS = "net_new_code"   # if nothing matches, assume ordinary feature code

# ---------------------------------------------------------------------------
# Industry essential-floor map (paper Table 5). Typical essential-fraction range
# and the whole-project speedup ceiling it implies (S_max = 1/phi).
# ---------------------------------------------------------------------------
INDUSTRY_CEILINGS = [
    ("Safety-critical / embedded (avionics, medical devices)", 0.55, 0.70),
    ("Regulated finance / healthcare enterprise",              0.40, 0.55),
    ("Enterprise integration / legacy modernization",          0.30, 0.45),
    ("General SaaS / product engineering",                     0.25, 0.35),
    ("Greenfield / prototype / internal tooling",              0.15, 0.25),
]


def normalize_difficulty(value) -> str | None:
    """Map a free-text difficulty cell to a canonical tier, or None."""
    if value is None:
        return None
    key = str(value).strip().lower()
    if not key:
        return None
    return DIFFICULTY_ALIASES.get(key)


import re as _re

_KW_PATTERNS = [(_re.compile(r"(?<![a-z0-9])" + _re.escape(kw)), cls)
                for kw, cls in KEYWORDS]


def classify_work(label: str) -> str:
    """
    Map a free-text work-item / work-class label to a canonical class key.

    Matching is anchored at a word start (no preceding letter/digit) so short
    keywords do not fire on substrings of unrelated words -- e.g. "ui" must not
    match "b(ui)lder", and "auth" is disambiguated from "authoring" by ordering.
    """
    if not label:
        return DEFAULT_CLASS
    text = str(label).strip().lower()
    for pat, cls in _KW_PATTERNS:
        if pat.search(text):
            return cls
    return DEFAULT_CLASS


def is_essential_label(label: str) -> bool:
    text = str(label or "").strip().lower()
    return any(kw in text for kw in ESSENTIAL_KEYWORDS)


def resolve_band(work_class_key: str, difficulty_tier: str | None):
    """
    Resolve a multiplier band (a_low, a_mode, a_high, essential).

    Priority:
      1. For ACCELERABLE (non-essential) work, a difficulty tier (if given) sets
         the band from Table 6.
      2. ESSENTIAL classes (requirements, architecture, coordination, compliance)
         keep their Table 3 taxonomy band even when a difficulty tier is supplied.
         Per the paper, essential/conceptual work is not sped up or slowed by an
         AI-difficulty label; it sets the ceiling and carries its own prior.
      3. Otherwise use the work-class default band.
    """
    cls_low, cls_mode, cls_high, essential = WORK_CLASS_PRIORS.get(
        work_class_key, WORK_CLASS_PRIORS[DEFAULT_CLASS]
    )
    if difficulty_tier and difficulty_tier in DIFFICULTY_BANDS and not essential:
        d_low, d_mode, d_high = DIFFICULTY_BANDS[difficulty_tier]
        return d_low, d_mode, d_high, essential
    return cls_low, cls_mode, cls_high, essential
