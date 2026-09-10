#!/usr/bin/env python3
"""
Author: Viquar Khan (ORCID 0009-0008-3592-4162).

Chart generation for the WCE report. Each function returns a base64-encoded PNG
so the HTML report is fully self-contained (no external image files needed).
"""

from __future__ import annotations

import base64
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BLUE = "#2563eb"
GREEN = "#16a34a"
RED = "#dc2626"
AMBER = "#d97706"
GREY = "#94a3b8"


def _b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def fig_summary_bar(res):
    """Baseline vs adjusted vs essential floor (calendar)."""
    fig, ax = plt.subplots(figsize=(6.2, 3.2))
    labels = ["Baseline", "AI-adjusted", "Essential floor"]
    vals = [res.baseline_calendar, res.adjusted_calendar, res.floor_calendar]
    colors = [GREY, BLUE, RED]
    bars = ax.bar(labels, vals, color=colors)
    ax.set_ylabel(f"calendar time ({_cal_unit(res.unit)})")
    ax.set_title("Where the estimate lands")
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.2f}",
                ha="center", va="bottom", fontsize=9)
    ax.margins(y=0.18)
    return _b64(fig)


def fig_ceiling(res):
    """Requested/achieved speedup against the Khan Ceiling band."""
    fig, ax = plt.subplots(figsize=(6.2, 3.2))
    ceil_s = res.ceiling_strict if res.ceiling_strict != float("inf") else 0
    ceil_g = res.ceiling_generous if res.ceiling_generous != float("inf") else 0
    ax.axhspan(ceil_s, ceil_g, color=GREEN, alpha=0.12,
               label="Khan Ceiling band (strict->generous)")
    ax.axhline(ceil_s, color=GREEN, ls="--", lw=1)
    ax.axhline(ceil_g, color=GREEN, ls="--", lw=1)
    ax.bar(["achieved\nspeedup"], [res.speedup], color=BLUE, width=0.5)
    ax.text(0, res.speedup, f"{res.speedup:.2f}x", ha="center", va="bottom", fontsize=10)
    if res.claim:
        cs = res.claim["implied_speedup"]
        ax.axhline(cs, color=RED, ls="-", lw=1.5,
                   label=f"claim {cs:.1f}x ({res.claim['verdict'].split()[0]})")
    ax.set_ylabel("whole-project speedup (x)")
    ax.set_title(f"Khan Ceiling: phi={res.phi:.2f}  =>  S_max = {ceil_s:.2f}-{ceil_g:.2f}x")
    ax.legend(fontsize=7, loc="upper right")
    top = max(res.speedup, ceil_g, res.claim.get("implied_speedup", 0) if res.claim else 0)
    ax.set_ylim(0, top * 1.25)
    return _b64(fig)


def fig_subsystems(res):
    """Per-subsystem baseline vs adjusted calendar."""
    subs = res.subsystems[:12]
    fig, ax = plt.subplots(figsize=(6.4, max(2.6, 0.45 * len(subs) + 1)))
    names = [s["subsystem"] for s in subs][::-1]
    base = [s["baseline_calendar"] for s in subs][::-1]
    adj = [s["adjusted_calendar"] for s in subs][::-1]
    y = range(len(names))
    ax.barh(y, base, color=GREY, label="baseline")
    ax.barh(y, adj, color=BLUE, label="AI-adjusted", height=0.5)
    ax.set_yticks(list(y))
    ax.set_yticklabels(names, fontsize=8)
    ax.set_xlabel(f"calendar time ({_cal_unit(res.unit)})")
    ax.set_title("Per-subsystem effort (baseline vs AI-adjusted)")
    ax.legend(fontsize=8, loc="lower right")
    return _b64(fig)


def fig_uncertainty(res):
    """Conditional vs total P10-P90 calendar bands with point estimate."""
    fig, ax = plt.subplots(figsize=(6.2, 2.8))
    rows = [("Conditional\n(fixed scope)", res.cond_p10_cal, res.cond_p50 / res.team_size,
             res.cond_p90_cal, BLUE),
            ("Total\n(+scope risk)", res.total_p10_cal, res.total_p50 / res.team_size,
             res.total_p90_cal, AMBER)]
    for i, (lab, lo, mid, hi, c) in enumerate(rows):
        ax.plot([lo, hi], [i, i], color=c, lw=6, solid_capstyle="round", alpha=0.5)
        ax.plot([mid], [i], "o", color=c, ms=9)
        ax.text(hi, i, f" P90 {hi:.2f}", va="center", fontsize=8)
        ax.text(lo, i, f"P10 {lo:.2f} ", va="center", ha="right", fontsize=8)
    ax.axvline(res.adjusted_calendar, color=GREEN, ls="--", lw=1,
               label=f"modal {res.adjusted_calendar:.2f}")
    ax.axvline(res.baseline_calendar, color=GREY, ls=":", lw=1,
               label=f"baseline {res.baseline_calendar:.2f}")
    ax.set_yticks([0, 1])
    ax.set_yticklabels([r[0] for r in rows], fontsize=8)
    ax.set_xlabel(f"calendar time ({_cal_unit(res.unit)})")
    ax.set_title("Uncertainty bands (200k Monte Carlo draws)")
    ax.legend(fontsize=7, loc="upper right")
    ax.set_ylim(-0.6, 1.6)
    return _b64(fig)


def fig_compare(baseline_cal, scenarios, unit):
    """Initial vs each scenario: bars (calendar) with P10-P90 whiskers."""
    cal = _cal_unit(unit)
    labels = ["Initial\nestimate"] + [s[0].replace(" ", "\n") for s in scenarios]
    vals = [baseline_cal] + [s[1].adjusted_calendar for s in scenarios]
    colors = [GREY] + [GREEN, BLUE, AMBER, RED][:len(scenarios)]
    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    x = range(len(labels))
    bars = ax.bar(x, vals, color=colors, width=0.6, zorder=3)
    # P10-P90 whiskers for scenarios (not the fixed initial estimate)
    for i, s in enumerate(scenarios, start=1):
        res = s[1]
        lo, hi = res.total_p10_cal, res.total_p90_cal
        ax.plot([i, i], [lo, hi], color="#334155", lw=1.5, zorder=4)
        ax.plot([i - 0.08, i + 0.08], [lo, lo], color="#334155", lw=1.5, zorder=4)
        ax.plot([i - 0.08, i + 0.08], [hi, hi], color="#334155", lw=1.5, zorder=4)
    for i, (b, v) in enumerate(zip(bars, vals)):
        pct = "" if i == 0 else f"\n-{(1 - v / baseline_cal) * 100:.0f}%"
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.1f}{pct}",
                ha="center", va="bottom", fontsize=9, zorder=5)
    ax.axhline(baseline_cal, color=GREY, ls=":", lw=1, zorder=1)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel(f"calendar time ({cal})")
    ax.set_title("Initial vs AI-adjusted estimate (whiskers = P10-P90 with scope risk)")
    ax.margins(y=0.22)
    return _b64(fig)


def _cal_unit(unit):
    u = unit.lower()
    if "month" in u:
        return "months"
    if "day" in u:
        return "days"
    if "hour" in u:
        return "hours"
    if "point" in u:
        return "points"
    return "units"


def build_all(res):
    return {
        "summary": fig_summary_bar(res),
        "ceiling": fig_ceiling(res),
        "subsystems": fig_subsystems(res),
        "uncertainty": fig_uncertainty(res),
    }
