#!/usr/bin/env python3
"""
Author: Viquar Khan (ORCID 0009-0008-3592-4162).

Core WCE estimation engine.

Implements the paper "No Silver Estimate: An Amdahl-Bounded Framework for
AI-Adjusted Software Effort Estimation" (Viquar Khan, ORCID 0009-0008-3592-4162):

    adjusted effort ratio      r      = sum_i f_i * a_i
    AI-adjusted effort         E_ai   = E * r
    whole-project speedup      S      = 1 / r
    Khan Ceiling (P1)          S_max  = 1 / sum_{i in essential} f_i * a_i^bestcase
    flat-discount error (P2)   M      = E * sum_i f_i * |a_i - r|
    Codegen Illusion (P3)      G      = r / a_focus

All quantities are computed both deterministically (modal) and via Monte Carlo
(triangular multiplier draws + Dirichlet share jitter + optional lognormal
baseline/scope uncertainty), matching estimation_framework.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np

SEED = 20260904
N_DRAWS = 200_000
SCOPE_SIGMA = 0.30          # residual baseline/scope uncertainty (lognormal)
SHARE_CONCENTRATION = 60.0  # Dirichlet concentration on the decomposition


@dataclass
class WorkItem:
    name: str
    subsystem: str
    baseline: float           # baseline effort in the workbook's effort unit
    a_low: float
    a_mode: float
    a_high: float
    essential: bool
    work_class: str = ""
    difficulty: str = ""
    source: str = ""          # how the band was resolved (for the audit trail)


@dataclass
class EstimationResult:
    unit: str
    team_size: float
    days_per_month: float = 21.0
    items: list = field(default_factory=list)
    # totals
    baseline_effort: float = 0.0
    adjusted_effort: float = 0.0
    r: float = 0.0
    speedup: float = 0.0
    net_reduction_pct: float = 0.0
    baseline_calendar: float = 0.0
    adjusted_calendar: float = 0.0
    calendar_saved: float = 0.0
    # P1 ceiling
    phi: float = 0.0
    ceiling_strict: float = 0.0
    ceiling_generous: float = 0.0
    floor_effort: float = 0.0
    floor_calendar: float = 0.0
    # P2 flat-discount error
    flat_discount_pct: float = 0.0
    misallocated_effort: float = 0.0
    misallocation_rows: list = field(default_factory=list)
    # P3 codegen illusion
    focus_class: str = ""
    focus_multiplier: float = 0.0
    activity_speedup: float = 0.0
    codegen_gap: float = 0.0
    # uncertainty
    cond_p10: float = 0.0
    cond_p50: float = 0.0
    cond_p90: float = 0.0
    total_p10: float = 0.0
    total_p50: float = 0.0
    total_p90: float = 0.0
    cond_p10_cal: float = 0.0
    cond_p90_cal: float = 0.0
    total_p10_cal: float = 0.0
    total_p90_cal: float = 0.0
    # per-subsystem rollup
    subsystems: list = field(default_factory=list)
    # difficulty distribution
    difficulty_mix: dict = field(default_factory=dict)
    # claim check (optional)
    claim: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)


def estimate(items: list[WorkItem], team_size: float = 1.0, unit: str = "person-months",
             claim_calendar: float | None = None, seed: int = SEED,
             n_draws: int = N_DRAWS, days_per_month: float = 21.0) -> EstimationResult:
    """Run the full WCE analysis over a flat list of work items."""
    if not items:
        raise ValueError("No work items to estimate.")

    rng = np.random.default_rng(seed)
    names = [it.name for it in items]
    base = np.array([it.baseline for it in items], dtype=float)
    a_lo = np.array([it.a_low for it in items], dtype=float)
    a_mo = np.array([it.a_mode for it in items], dtype=float)
    a_hi = np.array([it.a_high for it in items], dtype=float)
    ess = np.array([it.essential for it in items], dtype=bool)

    E = float(base.sum())
    if E <= 0:
        raise ValueError("Total baseline effort is zero; cannot estimate.")
    f = base / E                              # shares
    adj = base * a_mo                         # modal adjusted effort per item
    E_ai = float(adj.sum())
    r = E_ai / E
    speedup = 1.0 / r

    res = EstimationResult(unit=unit, team_size=team_size, days_per_month=days_per_month)
    res.items = items
    res.baseline_effort = round(E, 3)
    res.adjusted_effort = round(E_ai, 3)
    res.r = round(r, 4)
    res.speedup = round(speedup, 3)
    res.net_reduction_pct = round((1 - r) * 100, 1)
    res.baseline_calendar = round(E / team_size, 3)
    res.adjusted_calendar = round(E_ai / team_size, 3)
    res.calendar_saved = round((E - E_ai) / team_size, 3)

    # --- P1 Khan Ceiling ---------------------------------------------------
    phi = float(base[ess].sum()) / E if ess.any() else 0.0
    res.phi = round(phi, 4)
    if ess.any():
        ess_bestcase = float(np.sum(base[ess] * a_lo[ess])) / E
        res.ceiling_strict = round(1.0 / phi, 3) if phi > 0 else float("inf")
        res.ceiling_generous = round(1.0 / ess_bestcase, 3) if ess_bestcase > 0 else float("inf")
        res.floor_effort = round(E * phi, 3)
        res.floor_calendar = round(E * phi / team_size, 3)
    else:
        res.ceiling_strict = float("inf")
        res.ceiling_generous = float("inf")
        res.warnings.append(
            "No work items flagged essential; the Khan Ceiling is unbounded. "
            "Mark requirements/architecture/coordination/compliance work as essential.")

    # --- P2 Flat-discount error -------------------------------------------
    per_item_mis = f * np.abs(a_mo - r)
    res.flat_discount_pct = round((1 - r) * 100, 1)
    res.misallocated_effort = round(float(np.sum(per_item_mis)) * E, 3)
    order = np.argsort(per_item_mis)[::-1]
    for idx in order[:8]:
        flat_alloc = base[idx] * r
        true_alloc = base[idx] * a_mo[idx]
        res.misallocation_rows.append({
            "item": names[idx],
            "share": round(float(f[idx]), 4),
            "a_mode": round(float(a_mo[idx]), 3),
            "flat_effort": round(float(flat_alloc), 3),
            "true_effort": round(float(true_alloc), 3),
            "misallocation": round(float(true_alloc - flat_alloc), 3),
        })

    # --- P3 Codegen Illusion ----------------------------------------------
    i_focus = int(np.argmin(a_mo))
    a_focus = float(a_mo[i_focus])
    res.focus_class = names[i_focus]
    res.focus_multiplier = round(a_focus, 3)
    res.activity_speedup = round(1.0 / a_focus, 3)
    res.codegen_gap = round(r / a_focus, 3)

    # --- Monte Carlo -------------------------------------------------------
    # Draw order matches estimation_framework.py exactly (shares first via
    # Dirichlet, then per-class multipliers via triangular, then the lognormal
    # scope factor) so the tool reproduces the paper's published percentiles for
    # a given profile under the same seed.
    alpha = f * SHARE_CONCENTRATION
    alpha = np.clip(alpha, 1e-3, None)
    shares = rng.dirichlet(alpha, size=n_draws)
    mults = np.empty((n_draws, len(items)))
    for i in range(len(items)):
        if a_hi[i] - a_lo[i] < 1e-9:          # degenerate band -> fixed value
            mults[:, i] = a_mo[i]
        else:
            mults[:, i] = rng.triangular(a_lo[i], a_mo[i], a_hi[i], n_draws)
    r_s = np.sum(shares * mults, axis=1)
    eff_cond = E * r_s
    B = rng.lognormal(mean=-0.5 * SCOPE_SIGMA ** 2, sigma=SCOPE_SIGMA, size=n_draws)
    eff_total = eff_cond * B

    def p(a, q):
        return round(float(np.percentile(a, q)), 3)

    res.cond_p10, res.cond_p50, res.cond_p90 = p(eff_cond, 10), p(eff_cond, 50), p(eff_cond, 90)
    res.total_p10, res.total_p50, res.total_p90 = p(eff_total, 10), p(eff_total, 50), p(eff_total, 90)
    res.cond_p10_cal = round(res.cond_p10 / team_size, 3)
    res.cond_p90_cal = round(res.cond_p90 / team_size, 3)
    res.total_p10_cal = round(res.total_p10 / team_size, 3)
    res.total_p90_cal = round(res.total_p90 / team_size, 3)

    # --- Per-subsystem rollup ---------------------------------------------
    subs = {}
    for it in items:
        s = subs.setdefault(it.subsystem, {"baseline": 0.0, "adjusted": 0.0,
                                           "ess_base": 0.0, "count": 0})
        s["baseline"] += it.baseline
        s["adjusted"] += it.baseline * it.a_mode
        s["ess_base"] += it.baseline if it.essential else 0.0
        s["count"] += 1
    for name, s in subs.items():
        sr = s["adjusted"] / s["baseline"] if s["baseline"] else 1.0
        res.subsystems.append({
            "subsystem": name,
            "items": s["count"],
            "baseline": round(s["baseline"], 3),
            "adjusted": round(s["adjusted"], 3),
            "speedup": round(1.0 / sr, 3) if sr else 0.0,
            "net_reduction_pct": round((1 - sr) * 100, 1),
            "essential_pct": round(100 * s["ess_base"] / s["baseline"], 1) if s["baseline"] else 0.0,
            "baseline_calendar": round(s["baseline"] / team_size, 3),
            "adjusted_calendar": round(s["adjusted"] / team_size, 3),
        })
    res.subsystems.sort(key=lambda x: x["baseline"], reverse=True)

    # --- Difficulty mix ----------------------------------------------------
    mix = {}
    for it in items:
        key = (it.difficulty or "unspecified").lower()
        m = mix.setdefault(key, {"count": 0, "baseline": 0.0})
        m["count"] += 1
        m["baseline"] += it.baseline
    res.difficulty_mix = {k: {"count": v["count"],
                              "baseline": round(v["baseline"], 3),
                              "baseline_pct": round(100 * v["baseline"] / E, 1)}
                          for k, v in mix.items()}

    # --- Optional claim-rejection check -----------------------------------
    if claim_calendar is not None and claim_calendar > 0:
        claim_effort = claim_calendar * team_size
        implied_speedup = E / claim_effort
        p_below = float(np.mean(eff_total <= claim_effort))
        exceeds = bool(implied_speedup > res.ceiling_generous)
        res.claim = {
            "claim_calendar": round(claim_calendar, 3),
            "claim_effort": round(claim_effort, 3),
            "implied_speedup": round(implied_speedup, 3),
            "exceeds_generous_ceiling": exceeds,
            "prob_at_or_below_total": round(p_below, 6),
            "verdict": "REJECT (analytically impossible)" if exceeds else
                       ("IMPLAUSIBLE (below P10)" if p_below < 0.10 else "PLAUSIBLE"),
        }
    return res
