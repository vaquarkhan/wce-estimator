#!/usr/bin/env python3
"""
Author: Viquar Khan (ORCID 0009-0008-3592-4162).

WCE Estimator - command-line entry point.

Reads a multi-tab Excel workbook and writes a final estimation report
(Excel + self-contained HTML).

Usage:
    python estimate.py INPUT.xlsx [-o OUTDIR] [--team N] [--claim MONTHS]
                       [--sheets "A,B"] [--unit LABEL]
                       [--default-difficulty low|medium|high] [--compare] [--open]

Examples:
    python estimate.py my_project.xlsx
    python estimate.py my_project.xlsx -o reports --team 3 --claim 1
    python estimate.py loe.xlsx --sheets "Epic Summary" --unit developer-days --compare
"""

from __future__ import annotations

import argparse
import os
import sys
import webbrowser

from wce_estimator import (
    read_workbook, estimate, build_excel_report, build_html_report,
    build_comparison_report,
)


def _run_scenario(args, default_difficulty):
    """Read + estimate one scenario. Returns (res, project, unit, team, claim)."""
    include = [s.strip() for s in args.sheets.split(",")] if args.sheets else None
    items, config, warnings = read_workbook(
        args.input, include_sheets=include, default_difficulty=default_difficulty)
    team = args.team if args.team is not None else config.get("team_size", 1.0)
    unit = args.unit if args.unit is not None else config.get("unit", "person-months")
    claim = args.claim if args.claim is not None else config.get("claim_calendar")
    dpm = args.days_per_month if args.days_per_month is not None else config.get("days_per_month", 21.0)
    project = config.get("project") or os.path.splitext(os.path.basename(args.input))[0]
    res = estimate(items, team_size=team, unit=unit, claim_calendar=claim,
                   seed=args.seed, days_per_month=dpm)
    res.warnings = warnings + res.warnings
    return res, project, unit, team, claim


def _print_summary(res, project, unit, team):
    cal = _cal_unit(unit)
    print("=" * 68)
    print(f"WCE Estimation Report - {project}")
    print("=" * 68)
    print(f"  Work items          : {len(res.items)} across {len(res.subsystems)} subsystems")
    print(f"  Baseline effort     : {res.baseline_effort:.2f} {unit} "
          f"({res.baseline_calendar:.2f} {cal} @ {team:g} dev)")
    print(f"  AI-adjusted effort  : {res.adjusted_effort:.2f} {unit} "
          f"({res.adjusted_calendar:.2f} {cal})")
    print(f"  Speedup / reduction : {res.speedup:.2f}x  /  -{res.net_reduction_pct:.1f}%")
    print(f"  Essential phi       : {res.phi:.2f}  ->  Khan Ceiling "
          f"{_ceil(res.ceiling_strict)}-{_ceil(res.ceiling_generous)}x")
    print(f"  Absolute floor      : {res.floor_calendar:.2f} {cal} (nothing beats this)")
    print(f"  Total P10-P90       : {res.total_p10_cal:.2f}-{res.total_p90_cal:.2f} {cal}")
    print(f"  Flat-discount error : {res.misallocated_effort:.2f} {unit} misallocated (P2)")
    print(f"  Codegen illusion    : {res.codegen_gap:.2f}x gap (P3)")
    if res.claim:
        print(f"  Claim check         : {res.claim['claim_calendar']:.2f} {cal} "
              f"=> {res.claim['implied_speedup']:.2f}x  -> {res.claim['verdict']}")
    if res.warnings:
        print("  Notes:")
        for w in res.warnings:
            print(f"    - {w}")


COMPARE_INTRO = (
    "This report shows two scenarios for the same scope. <b>Realistic</b> treats "
    "each unclassified item as a mixed bundle (code + test + integration + review, "
    "AI effort multiplier a&asymp;0.75) and is the recommended figure. "
    "<b>Optimistic</b> assumes every unclassified item is pure net-new coding "
    "(a&asymp;0.55), an upper bound on the AI benefit. The gap between the two tabs "
    "is the cost of not labelling work classes; add <b>AI Difficulty</b> and "
    "<b>Essential</b> columns to collapse it.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="AI-adjusted effort estimation (WCE).")
    ap.add_argument("input", help="path to the multi-tab .xlsx workbook")
    ap.add_argument("-o", "--outdir", default=".", help="output directory (default: .)")
    ap.add_argument("--team", type=float, default=None,
                    help="team size (developers); overrides the Config sheet")
    ap.add_argument("--claim", type=float, default=None,
                    help="a claimed calendar duration to stress-test against the ceiling")
    ap.add_argument("--sheets", default=None,
                    help="comma-separated list of sheet/tab names to include "
                         "(use when a workbook has multiple views of the same scope)")
    ap.add_argument("--unit", default=None,
                    help="effort unit label override (e.g. 'developer-days')")
    ap.add_argument("--default-difficulty", default=None,
                    choices=["low", "medium", "high"],
                    help="AI-difficulty assumed for rows that could not be classified "
                         "(use 'medium' for coarse epic-level lists)")
    ap.add_argument("--days-per-month", type=float, default=None,
                    help="working days per month for the calendar-months view "
                         "(default 21; only used when the effort unit is days/hours)")
    ap.add_argument("--compare", action="store_true",
                    help="produce ONE report with Realistic + Optimistic tabs")
    ap.add_argument("--seed", type=int, default=20260904)
    ap.add_argument("--open", action="store_true", help="open the HTML report when done")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.input):
        ap.error(f"input file not found: {args.input}")

    os.makedirs(args.outdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(args.input))[0]
    html_path = os.path.join(args.outdir, f"{stem}_WCE_report.html")

    if args.compare:
        real_res, project, unit, team, _ = _run_scenario(args, "medium")
        opt_res, _, _, _, _ = _run_scenario(args, None)
        cal = _cal_unit(unit)
        scenarios = [
            ("Realistic", f"mixed bundles &middot; {real_res.adjusted_calendar:.1f} {cal} "
                          f"(-{real_res.net_reduction_pct:.0f}%)", real_res),
            ("Optimistic", f"pure-coding bound &middot; {opt_res.adjusted_calendar:.1f} {cal} "
                           f"(-{opt_res.net_reduction_pct:.0f}%)", opt_res),
        ]
        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(build_comparison_report(scenarios, project_name=project,
                                             intro=COMPARE_INTRO))
        # Excel: one workbook per scenario (clearly named)
        real_xlsx = os.path.join(args.outdir, f"{stem}_WCE_realistic.xlsx")
        opt_xlsx = os.path.join(args.outdir, f"{stem}_WCE_optimistic.xlsx")
        build_excel_report(real_res, real_xlsx)
        build_excel_report(opt_res, opt_xlsx)

        print("### REALISTIC (recommended) ###")
        _print_summary(real_res, project, unit, team)
        print("\n### OPTIMISTIC (upper bound) ###")
        _print_summary(opt_res, project, unit, team)
        print("-" * 68)
        print(f"  Combined HTML : {html_path}")
        print(f"  Excel (real)  : {real_xlsx}")
        print(f"  Excel (opt)   : {opt_xlsx}")
    else:
        res, project, unit, team, _ = _run_scenario(args, args.default_difficulty)
        xlsx_path = os.path.join(args.outdir, f"{stem}_WCE_report.xlsx")
        build_excel_report(res, xlsx_path)
        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(build_html_report(res, project_name=project))
        _print_summary(res, project, unit, team)
        print("-" * 68)
        print(f"  Excel report : {xlsx_path}")
        print(f"  HTML report  : {html_path}")

    if args.open:
        webbrowser.open("file://" + os.path.abspath(html_path))
    return 0


def _ceil(v):
    return "inf" if v == float("inf") else f"{v:.2f}"


def _cal_unit(unit):
    u = unit.lower()
    return ("months" if "month" in u else "days" if "day" in u else
            "hours" if "hour" in u else "points" if "point" in u else "units")


if __name__ == "__main__":
    sys.exit(main())
