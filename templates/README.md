# templates/ - the input workbooks

This folder holds the two spreadsheets you start from. You do not fill these in
place: copy one into `../input/`, edit your copy, then run the tool on it. These
two files are the only `.xlsx` tracked in git; anything you create in `../input/`
is git-ignored so your real data is never published.

| File | Use it when | Tabs |
|---|---|---|
| `WCE_blank_template.xlsx` | Estimating your own project. A full-SDLC skeleton: every process area is pre-listed as a greyed example row with a placeholder baseline. Keep what applies, delete what does not, replace the numbers. | Instructions, Discovery & Planning, Cloud & Infrastructure, Backend & Data, Frontend, Quality & Testing, Release & Ops, Config |
| `WCE_sample_example.xlsx` | You want to see the tool work immediately. A fully worked example (concurrent web app, 11 features) that reproduces the paper's Appendix C exactly: r = 0.819, 8.52 PM, phi = 0.231, Khan Ceiling 4.33-4.91x. | Instructions, Project (cross-cutting), Backend & Data, Frontend (React), Config |

## Do I have to use these templates?

**No. The templates are a convenience, not a requirement.** The tool reads *any*
`.xlsx` workbook, as long as each data sheet has:

1. a column it recognizes as the **work-item name** (Work Item, Task, Feature,
   Component, Module, Story, Epic, Requirement, Deliverable, Activity, Summary,
   Title, and variants like "Task Name"), and
2. a column it recognizes as **effort** (Baseline, Effort, Estimate, Days, Hours,
   PM, Person-Months, Story Points, Size, LOE, Duration, and variants like
   "Effort (days)" or "Estimate (days)").

Column matching is case-insensitive and tolerant of extra words and units, so
headers like `Task Name`, `Effort (hrs)`, or `Estimate (days)` are recognized.
A title row above the header is fine (the header is found within the first 25
rows). If a column name is not recognized, either rename it to one of the labels
above or use a template.

**Why the template still helps:** a bare "Task + Effort" sheet works, but every
row then falls back to net-new code (a is approximately 0.55) because it has no
Work Class or Essential markers. The template pre-labels each row's Work Class
and Essential flag, so you get accurate per-class multipliers and a meaningful
Khan Ceiling, and it lays out a full SDLC so nothing is missed.

## How the workbook is read

- **Each tab (worksheet) is a subsystem / module / phase.** Its name becomes the
  "subsystem" in the report's per-subsystem breakdown. Add, rename, or delete tabs
  freely.
- **Each row is one work item.** The tool sums every row across every tab into one
  project estimate.
- **Two special tabs** are treated differently:
  - A tab named `Config` (or `Settings`, `Meta`) is read as key/value settings,
    not work items.
  - A tab named `Instructions` (or `README`, `Notes`, `Help`, `Cover`, `Guide`)
    is ignored.
- **Rollup rows are skipped** automatically: a row whose Work Item is `TOTAL`,
  `Subtotal`, `Sum`, etc. is not counted, so your own totals do not double-count.
- A row is only counted if it has a Work Item name and a baseline effort greater
  than zero. Blank rows are ignored.

## Columns

Only two columns are required; the rest are optional and fill in from the model's
priors when left blank.

| Column | Required | What it does |
|---|---|---|
| **Work Item** | yes | The task/feature/component label. Also used to auto-classify if Work Class is blank. |
| **Baseline (PM)** | yes | Baseline effort (pre-AI). You may rename the header to `Effort`, `Estimate`, `Baseline`, `Days`, `Hours`, `Story Points`, `Dev Days`, `Total`, `LOE`. |
| **Work Class** | no | Names the category so the tool picks the right AI multiplier (see catalog below). If blank, the Work Item text is classified instead. |
| **AI Difficulty** | no | `Low` / `Medium` / `High`. An override that sets the multiplier band by tier. This is AI-resistance, not business size. Ignored for essential classes. |
| **Essential** | no | `Yes`/`No`. Marks work AI cannot remove (requirements, design, coordination, compliance, ceremonies). Essential work sets the Khan Ceiling (the floor no speedup can beat). If blank, the class default decides. |
| **a_low, a_mode, a_high** | no | An explicit multiplier band that overrides everything. Use it when you have your own calibrated number. |

Multiplier convention: `a < 1` means AI makes the item faster, `a = 1` no change,
`a > 1` slower (real for review, legacy integration, high-concurrency work).

## How a row gets its multiplier (resolution order)

1. **Explicit `a_low/a_mode/a_high`** if present, wins over everything.
2. Otherwise, if **AI Difficulty** is given and the class is not essential, the
   tier band is used.
3. Otherwise, the **Work Class** default band is used (matched from the Work
   Class text, or from the Work Item text if Work Class is blank).
4. If nothing matches, the item is treated as ordinary net-new feature code.

## Work-class catalog (built-in categories)

Put any of these in the **Work Class** column (matching is case-insensitive and by
keyword, so "REST API endpoints" and "Postgres schema" resolve correctly). `a` is
the modal multiplier; `essential` items set the ceiling.

| Work Class (type this) | Resolves to | a_low | a | a_high | Essential | Recognized keywords include |
|---|---|---|---|---|---|---|
| Requirements | requirements | 0.85 | 0.95 | 1.05 | yes | requirement, user story, discovery, elicitation |
| Architecture | architecture | 0.85 | 0.95 | 1.05 | yes | architecture, high/low-level design, technical design, api design |
| Data modeling | architecture | 0.85 | 0.95 | 1.05 | yes | data model, erd, entity relationship, schema design |
| UX design | ux_design | 0.75 | 0.88 | 1.05 | no | ux, ui design, wireframe, figma, mockup, prototype |
| Agile ceremonies | ceremonies | 0.98 | 1.00 | 1.05 | yes | sprint, standup, scrum, retro, refinement, demo, agile |
| Coordination | coordination | 0.95 | 1.00 | 1.05 | yes | coordination, stakeholder, meeting, kickoff, planning |
| Compliance | compliance | 0.95 | 1.05 | 1.15 | yes | compliance, regulatory, audit, sign-off, governance |
| Cloud infra | cloud_infra | 0.72 | 0.88 | 1.10 | no | cloud, terraform, iac, kubernetes, vpc, provisioning |
| Observability | observability | 0.65 | 0.80 | 1.00 | no | observability, monitoring, logging, metrics, alerting |
| Deployment | deployment | 0.75 | 0.90 | 1.10 | no | ci/cd, pipeline, deploy, release, devops, cutover |
| REST API | api_backend | 0.48 | 0.60 | 0.78 | no | rest, graphql, grpc, api, endpoint, backend, crud, webhook |
| Database | database | 0.58 | 0.70 | 0.88 | no | database, postgres, schema, sql, data access, orm, query |
| Concurrency | concurrency | 0.90 | 1.05 | 1.25 | no | concurrency, cache, scale, throughput |
| Security | security_auth | 0.85 | 0.95 | 1.10 | no | security, auth, otp, rbac, permission, oauth, encryption |
| Integration | integration | 0.90 | 1.10 | 1.35 | no | integration, legacy, third-party, reverse-engineer |
| Data migration | data_migration | 0.95 | 1.10 | 1.40 | no | data migration, migration, etl |
| React UI | frontend_ui | 0.58 | 0.70 | 0.90 | no | react, angular, vue, frontend, dashboard, page, component |
| Simple page | simple_page | 0.40 | 0.52 | 0.72 | no | simple page, static page, landing |
| Net-new code | net_new_code | 0.40 | 0.55 | 0.80 | no | feature, greenfield, implement, development (also the fallback) |
| Test planning | test_planning | 0.70 | 0.85 | 1.00 | no | test plan, test strategy, test case design |
| Test automation | test_automation | 0.50 | 0.65 | 0.85 | no | test automation, unit/integration/e2e test, selenium, cypress |
| Manual testing | manual_testing | 0.85 | 0.95 | 1.10 | no | manual test, exploratory, uat, user acceptance |
| Performance testing | performance_testing | 0.85 | 1.00 | 1.20 | no | performance test, load test, stress test, soak test |
| Review | review_rework | 0.95 | 1.15 | 1.45 | no | code review, review, rework, refactor, bug, defect, hotfix |
| Testing (generic) | testing | 0.60 | 0.80 | 1.05 | no | test, qa, validation, debug |
| Documentation | documentation | 0.45 | 0.60 | 0.80 | no | documentation, docs, runbook |
| Support | support | 0.85 | 0.95 | 1.10 | no | production support, on-call, maintenance |

### AI-difficulty tiers (the AI Difficulty column)

| Tier | a_low | a | a_high | Meaning |
|---|---|---|---|---|
| Low | 0.45 | 0.55 | 0.65 | AI accelerates strongly (well-patterned, local, cheap to verify) |
| Medium | 0.70 | 0.80 | 0.90 | AI helps with oversight (some integration or ambiguity) |
| High | 0.95 | 1.10 | 1.25 | AI neutral or slower (novel, safety/perf-critical, legacy) |

## Can I add my own categories?

- **New rows and new tabs: yes, unlimited.** This is the normal way to model your
  project. Name a tab per subsystem and add as many rows as you need.
- **New Work Class names: not directly.** The Work Class column maps to the fixed
  catalog above by keyword. If you type a class that is not recognized, the row
  falls back to net-new code. You have two supported ways to handle anything the
  catalog does not cover:
  1. Pick the closest existing class, or
  2. Set your own **a_low/a_mode/a_high** on that row. Explicit multipliers always
     win, so you never need a matching class.
- **A brand-new named class with its own default band: yes, but it is a code
  change, not a spreadsheet change.** Edit `../wce_estimator/priors.py`: add an
  entry to `WORK_CLASS_PRIORS` (band + essential flag) and one or more `KEYWORDS`
  that route to it. See `../wce_estimator/README.md` for the exact steps. This
  keeps every estimate auditable against a single, reviewed set of priors rather
  than ad-hoc per-spreadsheet categories.

## The Config tab

Key/value rows (all optional):

| Key | Example | Effect |
|---|---|---|
| Project | My Project | Report title. |
| Team Size | 2 | Developers; converts effort to calendar time. |
| Unit | person-months | Effort-unit label shown in the report. |
| Claim Months | 1 | A deadline claim to stress-test against the ceiling. |
| Working Days Per Month | 21 | Used for the calendar-months view when the unit is days. |

CLI flags (`--team`, `--unit`, `--claim`, `--days-per-month`) override the Config tab.

## Filling example (one row)

`Backend & Data` tab:

| Work Item | Work Class | Baseline (PM) | AI Difficulty | Essential |
|---|---|---|---|---|
| Orders REST API (CRUD) | REST API | 1.2 | | |

The tool classifies this as `api_backend` (a = 0.60), so the AI-adjusted effort
for the row is about 0.72 PM. Leaving AI Difficulty and Essential blank lets the
class prior decide.

## Limitations (know these before you rely on it)

- **File format: `.xlsx` (and `.xlsm`) only.** Legacy `.xls`, `.csv`, and Google
  Sheets links are not read; export them to `.xlsx` first. The web app accepts
  only `.xlsx`.
- **Formulas need cached values.** The reader uses the value Excel last saved for
  a formula cell. A workbook generated by another program and never opened in
  Excel may expose formula cells as blank; open and save it once, or paste values.
- **Header must be within the first 25 rows** of each sheet.
- **One effort column per sheet is used** (the leftmost recognized one). If you
  keep both `Estimate` and `Actual`, it uses the first recognized column.
- **Tabs are summed.** Two tabs describing the same scope (e.g. an epic summary
  and a story detail) double-count. Estimate one view, or run with
  `--sheets "TabName"` to include only one.
- **Merged cells** expose their value only in the top-left cell; the covered
  cells read as blank.
- **Number parsing** handles thousands separators (`1,200`), European decimal
  commas (`1,5`), and trailing units (`5 days` reads as 5). A cell with no number
  is skipped (the row is dropped if it has no valid effort).
- **Rows named TOTAL / Subtotal / Sum are skipped** as rollups.
- **Unrecognized Work Class values fall back to net-new code** (unless you set
  explicit `a_low/a_mode/a_high`).
- **The multipliers are priors, not measurements.** Treat the output as
  decision-support and recalibrate to your own historical actuals over time.

## Common mistakes

- **Two tabs describing the same scope** (e.g. an epic summary and a story detail)
  get summed and double-count. Estimate one view, or run with `--sheets "TabName"`
  to include only one.
- **Tagging construction work Essential.** Essential is for non-accelerable work
  (requirements, architecture, coordination, compliance, ceremonies). Over-tagging
  inflates the floor.
- **Confusing AI Difficulty with business complexity.** A gnarly business rule that
  is still ordinary code generation is Low AI-difficulty; a one-line change in a
  mature concurrent system is High.
- **No essential rows at all** makes the Khan Ceiling unbounded (the report warns).
  Tag your requirements/architecture/coordination work so the floor is meaningful.
