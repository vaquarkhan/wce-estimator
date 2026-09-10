# wce_estimator/ - the engine (Python package)

This package is the core of the tool. It implements the paper *"No Silver
Estimate: An Amdahl-Bounded Framework for AI-Adjusted Software Effort
Estimation"* (Viquar Khan). It has no UI: the CLI (`../estimate.py`) and the web
app (`../app.py`) are thin wrappers around it.

## Files

| File | What it does |
|---|---|
| `priors.py` | Multiplier libraries: AI-difficulty tiers (Table 6), the work-class catalog with default bands (Table 3 + extensions), the industry ceiling map, and the keyword classifier that maps a free-text label to a canonical class. Single source of truth for how a work item gets a multiplier band. |
| `engine.py` | The math. `estimate(items, ...)` computes `r = sum(f_i * a_i)`, whole-project speedup, the **Khan Ceiling** (P1), the flat-discount error (P2), the codegen illusion (P3), and the 200,000-draw Monte Carlo bands. Defines `WorkItem` and `EstimationResult`. |
| `reader.py` | Parses a multi-tab `.xlsx` into normalized `WorkItem`s: flexible column matching, difficulty/essential resolution, totals-row guard, ignore/config sheets, sheet selection, and an optional default-difficulty for unclassified rows. |
| `figures.py` | matplotlib charts, returned as base64 PNGs so the HTML report is self-contained. |
| `report.py` | Builds the Excel report and the self-contained HTML report (Overview + Realistic + Optimistic tabs, plus the concepts/formulas explainer). |
| `__init__.py` | Public API: `read_workbook`, `estimate`, `build_excel_report`, `build_comparison_report`, `build_html_report`. |

## The model in one screen

```
f_i   = share of baseline effort in work class i   (sum f_i = 1)
a_i   = AI effort multiplier for class i            (<1 faster, 1 same, >1 slower)
r     = sum(f_i * a_i)          adjusted effort ratio
E_ai  = E * r                   AI-adjusted effort
S     = 1 / r                   whole-project speedup
S_max = 1 / phi                 Khan Ceiling (phi = essential, non-accelerable share)
M     = E * sum(f_i*|a_i - r|)  flat-discount misallocation (P2)
G     = r / a_focus             codegen-illusion gap (P3)
```

## How a multiplier band is resolved (`priors.resolve_band`)

1. Explicit `a_low/a_mode/a_high` on the row wins (handled in `reader.py`).
2. Else, if an AI-difficulty tier is given and the class is **not essential**, the
   tier band (`DIFFICULTY_BANDS`) is used.
3. Else, the work-class default band (`WORK_CLASS_PRIORS`) is used.

Essential classes (requirements, architecture, coordination, compliance,
ceremonies) keep their taxonomy band even when a difficulty tier is supplied,
because conceptual/coordination work is not sped up or slowed by an AI-difficulty
label; it sets the ceiling.

Classification (`priors.classify_work`) matches keywords at word starts, so short
keywords do not fire inside unrelated words (e.g. `ui` does not match `builder`)
and ordering disambiguates (`authoring` is caught before `auth`).

## Use as a library

```python
from wce_estimator import read_workbook, estimate, build_comparison_report

items, config, warnings = read_workbook("input/my_project.xlsx")
res = estimate(items, team_size=2, unit="person-months")
print(res.adjusted_effort, res.speedup, res.ceiling_strict, res.ceiling_generous)
```

## Adding a new work class (developer change)

Spreadsheets cannot define new categories on their own; new named classes live
here so every estimate is auditable against one reviewed set of priors. To add
one, edit `priors.py`:

1. Add a band to `WORK_CLASS_PRIORS`, keyed by a canonical name:
   ```python
   "ml_training": (0.75, 0.90, 1.10, False),  # (a_low, a_mode, a_high, essential)
   ```
   Set `essential=True` only for non-accelerable conceptual/coordination work
   (it raises the Khan Ceiling floor).
2. Add one or more routing keywords to `KEYWORDS`, placing more specific terms
   before generic ones (first match wins):
   ```python
   ("model training", "ml_training"),
   ("fine-tune", "ml_training"),
   ```
3. If the class is essential and might arrive with explicit multipliers, add its
   keyword to `ESSENTIAL_KEYWORDS` too.

No other file needs changing; the reader, engine, and reports pick it up.

## Fidelity to the paper

The engine reproduces the paper's reproducible model (`estimation_framework.py`)
exactly: same formulas, same Monte Carlo parameters (seed 20260904, 200k draws,
scope sigma 0.30, Dirichlet concentration 60, same draw order), and the same
Table 3 work-class bands. The shipped sample reproduces Appendix C to the number.
The extension classes (cloud infra, observability, UX, the testing tiers, agile
ceremonies, support, documentation, data migration) are additions beyond the
paper's eight-class taxonomy, with multipliers chosen to follow the same logic.
