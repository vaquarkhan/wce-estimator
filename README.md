# WCE Estimator

A tool that turns a multi-tab Excel workbook into a final AI-adjusted software
effort estimate and report. It implements the framework from the paper:

> **No Silver Estimate: An Amdahl-Bounded Framework for AI-Adjusted Software
> Effort Estimation, an Industry Ceiling Map, and a Pattern Language**
> Viquar Khan (ORCID 0009-0008-3592-4162).

You give it your work breakdown (one tab per subsystem, one row per work item);
it returns the adjusted effort, the whole-project speedup, the **Khan Ceiling**
(the floor no amount of AI can beat), an uncertainty band, and the two classic
failure modes the paper formalizes (flat-discount error and the codegen illusion).

## What the report looks like

The tool produces one self-contained HTML page. The **Overview** tab leads with
the calendar-months bottom line, KPI cards, an initial-vs-adjusted comparison
chart, a side-by-side table, and a plain-language Khan Ceiling / WCE explainer:

![Overview tab of the WCE report](docs/images/overview.png)

The **Realistic** and **Optimistic** tabs give the full per-scenario detail: KPIs,
the where-it-lands and ceiling charts, uncertainty bands, the per-subsystem
breakdown, the flat-discount error table, and every work item with its resolved
multiplier:

![Realistic detail tab of the WCE report](docs/images/realistic-tab.png)

*(Screenshots generated from `templates/WCE_sample_example.xlsx`.)*

## What it computes

| Symbol | Meaning |
|---|---|
| `r = Σ fᵢaᵢ` | AI-adjusted effort ratio (share-weighted multipliers) |
| `E_ai = E·r` | AI-adjusted effort |
| `S = 1/r` | whole-project speedup |
| `S_max = 1/φ` | **Khan Ceiling** (P1): essential fraction φ caps the speedup |
| `M = E·Σ fᵢ|aᵢ−r|` | flat-discount misallocation (P2) |
| `G = r/a_focus` | activity-delivery gap / codegen illusion (P3) |

Uncertainty is a 200,000-draw Monte Carlo (triangular multipliers, Dirichlet
share jitter, lognormal scope risk; seed 20260904), reported as P10-P90 bands.

## Project layout

```
wce-estimator/
  wce_estimator/     the engine (Python package) - the code
  app.py             web app (upload in a browser)
  estimate.py        command-line tool
  requirements.txt   dependencies
  templates/         DOWNLOAD a template from here
                       WCE_blank_template.xlsx   (empty, start here)
                       WCE_sample_example.xlsx   (worked example, run as-is)
  input/             PUT your filled workbook here (your data; git-ignored)
  reports/           OUTPUT lands here (created automatically; git-ignored)
```

Which folder does what:
- `templates/` -> copy a template FROM here.
- `input/`     -> save your filled-in workbook HERE.
- `reports/`   -> the tool writes the final report HERE.

Your real workbooks in `input/` and everything in `reports/` are git-ignored, so
they never get published.

## Quick start

### 1. Build (install dependencies) - one time

```
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```
Requires Python 3.9+ (numpy, openpyxl, matplotlib, Flask).

### 2. Get a template and fill it in

Copy `templates/WCE_blank_template.xlsx` into `input/` and fill it in
(one tab per subsystem, one row per work item, see the `Instructions` tab inside
the workbook or "Input format" below). Save it as, e.g., `input/my_project.xlsx`.

To try it immediately without editing anything, use the worked example
`templates/WCE_sample_example.xlsx`.

### 3a. Run and generate the report - command line

```
python estimate.py input/my_project.xlsx -o reports --compare --open
```
This writes, into `reports/`:
- `my_project_WCE_report.html`  (the report: Overview + Realistic + Optimistic tabs)
- `my_project_WCE_realistic.xlsx` and `my_project_WCE_optimistic.xlsx`

`--open` launches the HTML report in your browser automatically.

Common options:
- `-o reports` output folder
- `--compare` ONE report with **Overview + Realistic + Optimistic** tabs (recommended)
- `--team N` team size (developers) for calendar time
- `--claim MONTHS` stress-test a deadline claim against the ceiling
- `--unit LABEL` effort-unit label (e.g. `developer-days`)
- `--days-per-month N` working days per month for the months view (default 21)
- `--sheets "A,B"` only include these tabs (when a workbook has several views of
  the same scope, e.g. an Epic summary and a Story detail, that must not be summed)
- `--default-difficulty low|medium|high` assumption for rows you did not classify
  (use `medium` for coarse epic-level lists)

### 3b. Run - web app (upload in a browser)

```
python app.py
```
Open http://127.0.0.1:5000, download the blank template (or the sample), fill it
in, upload it, and read the report on screen. Excel downloads are offered at the
top. (Localhost only, single user, see Security below.)

## Input format

The templates are optional. The tool reads **any `.xlsx`** as long as each data
sheet has a recognizable **work-item name** column and an **effort** column
(headers are matched case-insensitively and tolerate variants like `Task Name`
or `Effort (days)`). Using a template just pre-labels Work Class / Essential so
you get accurate multipliers. See `templates/README.md` for the full column and
work-class reference.

- **Each tab** = a subsystem / module / project area.
- **Each row** = a work item.
- **Required columns:** `Work Item` and a baseline effort column
  (`Baseline (PM)`, `Effort`, `Estimate`, `Days`, `Hours`, `Story Points`, ...).
- **Optional columns** (auto-filled from the paper's priors when blank):
  - `Work Class` - covers a full SDLC: Requirements / Architecture / Data modeling /
    UX design / Agile ceremonies / Compliance / Coordination / Cloud infra /
    Observability / Deployment (CI/CD) / REST API / Database / Integration /
    Security / Concurrency / Data migration / React UI / Simple page /
    Test planning / Test automation / Manual testing / Performance testing /
    Review / Documentation / Support
  - `AI Difficulty` - `Low` / `Medium` / `High` (AI-resistance, **not** business
    complexity)
  - `Essential` - `Yes`/`No` (work AI cannot drive to zero; sets the Khan Ceiling)
  - `a_low`, `a_mode`, `a_high` - an explicit multiplier band that overrides
    everything else
- **Optional `Config` tab** (key/value rows): `Team Size`, `Unit`, `Claim Months`,
  `Project`.

Multiplier convention: `a < 1` faster, `a = 1` unchanged, `a > 1` slower.

Resolution priority for each item's band: explicit multipliers → AI-difficulty
tier (non-essential classes) → work-class default. Essential classes keep their
own multiplier even if you tag a difficulty. Full column and work-class reference
is in `templates/README.md`.

### Extending

- Add as many **rows and tabs** as you like; that is the normal way to model a
  project.
- The **Work Class** column maps to a fixed, reviewed catalog (see
  `templates/README.md`). For anything it does not cover, either pick the closest
  class or set explicit `a_low/a_mode/a_high` on that row (which overrides the
  class).
- To add a **brand-new named class** with its own default band, edit
  `wce_estimator/priors.py` (`WORK_CLASS_PRIORS` + `KEYWORDS`); steps are in
  `wce_estimator/README.md`.

## Report layout (compare mode)

A single self-contained HTML page with three tabs:

1. **Overview** (landing) - the initial estimate vs the Realistic and Optimistic
   AI-adjusted numbers, a comparison chart with P10-P90 whiskers, a side-by-side
   table, and a plain-language explainer of the **Khan Ceiling / WCE** concept
   with all the formulas and how each number is calculated.
2. **Realistic** - full detail for the recommended scenario (unclassified rows
   treated as mixed bundles, a≈0.75).
3. **Optimistic** - full detail for the upper-bound scenario (unclassified rows
   treated as pure net-new coding, a≈0.55).

Each detail tab has KPIs, the where-it-lands and ceiling charts, uncertainty
bands, per-subsystem breakdown, the flat-discount error table, and every work
item with its resolved multiplier.

## Output files

- **HTML report** (self-contained, charts embedded as base64 - no external files).
- **Excel report(s)** with sheets: Summary, Work Items, Subsystems,
  Flat-Discount Error, Difficulty Mix (+ Notes if the parser had warnings). In
  `--compare` mode one Excel is written per scenario.

## Structure

```
wce-estimator/
  wce_estimator/
    priors.py       multiplier priors: difficulty tiers, work-class defaults, industry map
    engine.py       core WCE math (P1/P2/P3 + Monte Carlo)
    reader.py       multi-tab workbook parser -> normalized work items
    figures.py      matplotlib charts (base64 for self-contained HTML)
    report.py       Excel + HTML report builders (Overview + scenario tabs)
  estimate.py       CLI (add --compare for the 3-tab report)
  app.py            Flask upload UI
  templates/        WCE_blank_template.xlsx, WCE_sample_example.xlsx (+ README)
  input/            put your filled workbook here (README only; data git-ignored)
  requirements.txt
```

All Python files carry the author header (Viquar Khan, ORCID 0009-0008-3592-4162).

## Security & privacy (read before publishing or hosting)

- **No secrets in the code.** The source contains no credentials, keys, tokens,
  or hardcoded machine paths. The only personal data is the author attribution.
- **Your data stays out of git.** `.gitignore` ignores every `*.xlsx` by default
  and only whitelists the two synthetic templates in `templates/`. It also
  ignores `input/` data, `temp/`, `reports/`, `out/`, and `*.zip`, so real
  project workbooks and any generated reports are never committed. Verify with:
  ```
  git status --ignored
  git check-ignore -v <file>
  ```
- **Keep real workbooks and reports local.** Put confidential inputs under
  `input/` and send outputs to `reports/` (both git-ignored). Never force-add
  (`git add -f`) a data file.
- **The web app is localhost-only and unauthenticated.** `app.py` binds
  `127.0.0.1`, runs with `debug=False`, and caps uploads at 16 MB. Uploads are
  processed in a temporary directory and are not persisted to disk. Do **not**
  expose it on `0.0.0.0` or deploy it to a shared/public host without adding
  authentication and a production WSGI server (e.g. waitress/gunicorn) in front.
- **Uploaded workbooks are untrusted input.** Only `.xlsx` is accepted and it is
  parsed with openpyxl (no macro execution). Treat any workbook you did not
  create as untrusted.

## Limitations

- **File format:** `.xlsx` / `.xlsm` only. Export `.xls`, `.csv`, or Google
  Sheets to `.xlsx` first. The web app accepts only `.xlsx` (max 16 MB).
- **Formulas** are read from Excel's cached value; a workbook never opened in
  Excel may show formula cells as blank (open and save once, or paste values).
- **Header row** must be within the first 25 rows of a sheet.
- **One effort column per sheet** is used (leftmost recognized).
- **Tabs are summed** - two tabs of the same scope double-count; use `--sheets`
  to pick one.
- **Number parsing** handles thousands separators, European decimal commas, and
  trailing units (`5 days` -> 5); a cell with no number is skipped.
- **Rows named TOTAL / Subtotal / Sum** are skipped as rollups.
- **Unrecognized Work Class** values fall back to net-new code unless you set
  explicit `a_low/a_mode/a_high`.
- Full list and details: `templates/README.md`.

## Note

This is decision-support tooling, not a guarantee. Multiplier priors are
anchored to published field studies but should be recalibrated to your own
historical data (see the paper's longitudinal calibration rule).
