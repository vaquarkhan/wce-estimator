#!/usr/bin/env python3
"""
Author: Viquar Khan (ORCID 0009-0008-3592-4162).

WCE Estimator - Flask web app.

Upload a multi-tab Excel workbook and get the final AI-adjusted estimation
report rendered in the browser, with a one-click Excel download.

Run:
    python app.py
    # then open http://127.0.0.1:5000

No data is persisted: uploads are processed in a temp dir and the generated
Excel report is held in memory only for the current session's download link.
"""

from __future__ import annotations

import io
import os
import tempfile
import uuid

from flask import (
    Flask, request, render_template_string, send_file, abort, redirect, url_for,
)

from wce_estimator import (
    read_workbook, estimate, build_excel_report, build_comparison_report,
)

COMPARE_INTRO = (
    "This report shows two scenarios for the same scope. <b>Realistic</b> treats "
    "each unclassified item as a mixed bundle (code + test + integration + review, "
    "AI effort multiplier a&asymp;0.75) and is the recommended figure. "
    "<b>Optimistic</b> assumes every unclassified item is pure net-new coding "
    "(a&asymp;0.55), an upper bound on the AI benefit. Add <b>AI Difficulty</b> and "
    "<b>Essential</b> columns to your workbook to collapse the gap between them.")


def _cal_unit(unit):
    u = unit.lower()
    return ("months" if "month" in u else "days" if "day" in u else
            "hours" if "hour" in u else "points" if "point" in u else "units")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB upload cap

# in-memory store of generated Excel reports, keyed by token (bounded)
_REPORTS: dict[str, tuple[str, bytes]] = {}
_MAX_REPORTS = 32

UPLOAD_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WCE Estimator</title>
<style>
  body {font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:#f8fafc;
        color:#0f172a;margin:0;}
  header{background:#1e3a8a;color:#fff;padding:30px 32px;}
  header h1{margin:0 0 4px;font-size:24px;}
  header p{margin:0;opacity:.85;font-size:14px;}
  main{max-width:720px;margin:0 auto;padding:32px;}
  .card{background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:28px;margin:18px 0;}
  .drop{border:2px dashed #93a3b8;border-radius:12px;padding:38px;text-align:center;
        background:#f8fafc;cursor:pointer;}
  .drop.hover{border-color:#1e3a8a;background:#eff6ff;}
  input[type=file]{display:none;}
  .row{display:flex;gap:16px;flex-wrap:wrap;margin-top:16px;}
  .row label{font-size:13px;color:#475569;display:block;margin-bottom:4px;}
  .row input{padding:8px 10px;border:1px solid #cbd5e1;border-radius:8px;width:140px;}
  button{background:#1e3a8a;color:#fff;border:0;border-radius:9px;padding:12px 22px;
         font-size:15px;cursor:pointer;margin-top:18px;}
  button:hover{background:#1d4ed8;}
  a.tmpl{color:#1e3a8a;font-size:13px;}
  .err{background:#fef2f2;border:1px solid #fecaca;color:#991b1b;padding:12px 16px;
       border-radius:10px;margin:14px 0;font-size:14px;}
  ul{color:#475569;font-size:14px;line-height:1.7;}
  code{background:#f1f5f9;padding:1px 6px;border-radius:5px;}
</style></head><body>
<header><h1>WCE Estimator</h1>
  <p>Upload a multi-tab Excel workbook &middot; get a final AI-adjusted effort estimate</p></header>
<main>
  {% if error %}<div class="err">{{ error }}</div>{% endif %}
  <div class="card">
    <form method="post" action="{{ url_for('run') }}" enctype="multipart/form-data" id="f">
      <label class="drop" id="drop">
        <input type="file" name="workbook" id="file" accept=".xlsx" required>
        <div id="dtext"><b>Click to choose</b> or drag your <code>.xlsx</code> here</div>
      </label>
      <div class="row">
        <div><label>Team size (devs)</label><input type="number" step="0.5" min="0.5"
             name="team" placeholder="from Config"></div>
        <div><label>Claim to test</label><input type="number" step="0.25" min="0"
             name="claim" placeholder="optional"></div>
        <div><label>Unit label</label><input type="text" name="unit"
             placeholder="e.g. developer-days" style="width:170px"></div>
        <div><label>Only these tabs</label><input type="text" name="sheets"
             placeholder="e.g. Epic Summary" style="width:200px"></div>
        <div><label>Working days / month</label><input type="number" step="1" min="1"
             name="dpm" placeholder="21"></div>
      </div>
      <button type="submit">Estimate</button>
    </form>
  </div>
  <div class="card">
    <h3 style="margin-top:0;color:#1e3a8a;">How it works</h3>
    <ul>
      <li>Each <b>tab</b> = a subsystem / module. Each <b>row</b> = a work item.</li>
      <li>Required: a <b>Work Item</b> column and a baseline effort column
          (e.g. <code>Baseline (PM)</code>, <code>Effort</code>, <code>Days</code>).</li>
      <li>Optional <b>Work Class</b>, <b>AI Difficulty</b> (Low/Medium/High),
          <b>Essential</b> (Yes/No) auto-fill from the framework's priors.</li>
      <li>Optional <b>Config</b> tab sets Team Size, Unit, and a Claim.</li>
    </ul>
    <p><a class="tmpl" href="{{ url_for('template') }}">&#8681; Download the blank template</a>
       &nbsp;&middot;&nbsp;
       <a class="tmpl" href="{{ url_for('sample') }}">&#8681; Download a filled sample</a></p>
  </div>
</main>
<script>
  const drop=document.getElementById('drop'),file=document.getElementById('file'),
        dtext=document.getElementById('dtext');
  file.addEventListener('change',()=>{if(file.files.length)dtext.innerHTML='<b>'+file.files[0].name+'</b> selected';});
  ['dragover','dragenter'].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.classList.add('hover');}));
  ['dragleave','drop'].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.classList.remove('hover');}));
  drop.addEventListener('drop',ev=>{file.files=ev.dataTransfer.files;
     if(file.files.length)dtext.innerHTML='<b>'+file.files[0].name+'</b> selected';});
</script>
</body></html>"""


def _store_report(name: str, data: bytes) -> str:
    if len(_REPORTS) >= _MAX_REPORTS:
        _REPORTS.pop(next(iter(_REPORTS)))
    token = uuid.uuid4().hex
    _REPORTS[token] = (name, data)
    return token


@app.route("/")
def index():
    return render_template_string(UPLOAD_PAGE, error=None)


_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")


@app.route("/template")
def template():
    """Blank, ready-to-fill full-SDLC workbook (shipped in templates/)."""
    path = os.path.join(_TEMPLATES_DIR, "WCE_blank_template.xlsx")
    if not os.path.isfile(path):
        abort(404)
    return send_file(path, as_attachment=True, download_name="WCE_blank_template.xlsx")


@app.route("/sample")
def sample():
    """Fully worked example (concurrent web app, 11 features), shipped in templates/."""
    path = os.path.join(_TEMPLATES_DIR, "WCE_sample_example.xlsx")
    if not os.path.isfile(path):
        abort(404)
    return send_file(path, as_attachment=True, download_name="WCE_sample_example.xlsx")


@app.route("/run", methods=["POST"])
def run():
    up = request.files.get("workbook")
    if not up or not up.filename:
        return render_template_string(UPLOAD_PAGE, error="Please choose an .xlsx file.")
    if not up.filename.lower().endswith(".xlsx"):
        return render_template_string(UPLOAD_PAGE, error="Only .xlsx workbooks are supported.")

    sheets_raw = (request.form.get("sheets") or "").strip()
    include = [s.strip() for s in sheets_raw.split(",") if s.strip()] or None
    unit_override = (request.form.get("unit") or "").strip() or None

    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "upload.xlsx")
        up.save(path)

        def build(default_difficulty):
            items, config, warnings = read_workbook(
                path, include_sheets=include, default_difficulty=default_difficulty)
            team = _num(request.form.get("team")) or config.get("team_size", 1.0)
            claim = _num(request.form.get("claim")) or config.get("claim_calendar")
            dpm = _num(request.form.get("dpm")) or config.get("days_per_month", 21.0)
            unit = unit_override or config.get("unit", "person-months")
            project = config.get("project") or os.path.splitext(up.filename)[0]
            res = estimate(items, team_size=team, unit=unit, claim_calendar=claim,
                           days_per_month=dpm)
            res.warnings = warnings + res.warnings
            return res, project, unit

        try:
            real_res, project, unit = build("medium")
            opt_res, _, _ = build(None)
        except Exception as exc:
            return render_template_string(UPLOAD_PAGE, error=f"Could not process workbook: {exc}")

        cal = _cal_unit(unit)
        rbuf, obuf = io.BytesIO(), io.BytesIO()
        build_excel_report(real_res, rbuf)
        build_excel_report(opt_res, obuf)
        rtok = _store_report(f"{project}_WCE_realistic.xlsx", rbuf.getvalue())
        otok = _store_report(f"{project}_WCE_optimistic.xlsx", obuf.getvalue())

        scenarios = [
            ("Realistic", f"mixed bundles &middot; {real_res.adjusted_calendar:.1f} {cal} "
                          f"(-{real_res.net_reduction_pct:.0f}%)", real_res),
            ("Optimistic", f"pure-coding bound &middot; {opt_res.adjusted_calendar:.1f} {cal} "
                           f"(-{opt_res.net_reduction_pct:.0f}%)", opt_res),
        ]
        html = build_comparison_report(scenarios, project_name=project, intro=COMPARE_INTRO)

        # inject a download bar at the top of the report
        bar = (f'<div style="background:#0f172a;padding:10px 32px;text-align:right">'
               f'<a href="{url_for("download", token=rtok)}" '
               f'style="color:#fff;font:600 14px sans-serif;text-decoration:none">'
               f'&#8681; Excel (realistic)</a> &nbsp;'
               f'<a href="{url_for("download", token=otok)}" '
               f'style="color:#cbd5e1;font:14px sans-serif;text-decoration:none">'
               f'&#8681; Excel (optimistic)</a> &nbsp;&nbsp;'
               f'<a href="{url_for("index")}" '
               f'style="color:#93c5fd;font:14px sans-serif;text-decoration:none">'
               f'New upload</a></div>')
        return html.replace("<body>", "<body>" + bar, 1)


@app.route("/download/<token>")
def download(token):
    entry = _REPORTS.get(token)
    if not entry:
        abort(404)
    name, data = entry
    return send_file(io.BytesIO(data), as_attachment=True, download_name=name,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def _num(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    print("WCE Estimator running at http://127.0.0.1:5000  (Ctrl+C to stop)")
    app.run(host="127.0.0.1", port=5000, debug=False)
