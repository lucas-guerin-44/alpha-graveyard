#!/usr/bin/env python3
"""
Structural-flow calendar audit — v3 (2026-05-29).

Widens v2 toward the **corr-gap** (#3: the book lacks non-US / non-equity / tail-convex legs)
and folds in this session's validated win (Nikkei SQ-open SHORT, lesson #87):

  - JPN225 Nikkei quarterly SQ **open** (2nd Fri Mar/Jun/Sep/Dec, 09:00-10:00 Tokyo) — the
    validated cell, now formally in the screen (sanity-check: the engine should flag it).
  - JPN225 Japan **quarter-end** + **month-end** Tokyo-close windows (new — window-dressing /
    fiscal repatriation flow; never screened).
  - EUSTX50 (Eurex, large options complex) added to the triple-witch + MSCI rebalance cells.

Reuses v2's corrected cost floors + full grid by import (DRY); adds JPN225/EUSTX50 floors + the
Nikkei SQ calendar. **Read survivors through the corr-gap lens**: a JP / FX / non-equity cell that
fills the book's hole is worth more than another US-index-close cell (redundant with the deployed book).

Usage:
  venv/Scripts/python.exe experiments/structural_flow_audit/structural_flow_audit_v3.py
"""
from __future__ import annotations

import os
import sys
from datetime import date

import numpy as np  # noqa: F401
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import structural_flow_audit as sfa  # noqa: E402
from structural_flow_audit import (  # noqa: E402
    section, load_m5, evaluate_grid, nth_weekday_of_month,
    gen_jpm_collar_dates, gen_month_end_dates, gen_triple_witch_dates, YEARS,
)
from structural_flow_audit_v2 import build_grids_v2, gen_msci_rebal_dates, CORRECTED_COST_FLOOR_BPS  # noqa: E402

# cost floors = v2 corrected + Japan/EU index venues (Eightcap Raw all-in RT bps)
COST_FLOOR_V3 = dict(CORRECTED_COST_FLOOR_BPS)
COST_FLOOR_V3.update({"JPN225": 1.0, "EUSTX50": 1.0})
sfa.COST_FLOOR_BPS = COST_FLOOR_V3

TOKYO = "Asia/Tokyo"
BERLIN = "Europe/Berlin"
LONDON = "Europe/London"
ET = "US/Eastern"


def gen_nikkei_sq_dates(years: range) -> list[date]:
    """Nikkei quarterly SQ = 2nd Friday of Mar/Jun/Sep/Dec (open-settled)."""
    out = []
    for y in years:
        for m in (3, 6, 9, 12):
            try:
                out.append(nth_weekday_of_month(y, m, weekday=4, n=2))
            except ValueError:
                continue
    return out


def build_grids_v3():
    grids = list(build_grids_v2())
    grids += [
        # ---- v3: Asian / Japan venue (corr-gap: non-US) ----
        ("nikkei_sq_open_jp", gen_nikkei_sq_dates, [
            ("JPN225", TOKYO, (9, 0, 10, 0))]),
        ("japan_quarter_end_close", gen_jpm_collar_dates, [
            ("JPN225", TOKYO, (14, 0, 15, 0))]),
        ("japan_month_end_close", gen_month_end_dates, [
            ("JPN225", TOKYO, (14, 0, 15, 0))]),
        # ---- v3: EUSTX50 (Eurex) added to EU settlement / rebalance cells ----
        ("triple_witch_close_eustx", gen_triple_witch_dates, [
            ("EUSTX50", BERLIN, (16, 30, 17, 30))]),
        ("msci_rebal_eustx", gen_msci_rebal_dates, [
            ("EUSTX50", BERLIN, (16, 30, 17, 30))]),
    ]
    return grids


# corr-gap tag for the ranked output (editorial): which cells fill the book's hole
GAP_FILL = {"JPN225", "EUSTX50", "EURUSD", "USDJPY", "GBPUSD", "XAUUSD"}  # non-US-index / FX / metals


def main() -> int:
    section("Structural-flow calendar audit v3 (corrected costs + Asian/Japan + EUSTX50)")
    print(f"  Period   : {sfa.START_DATE} -> {sfa.END_DATE}")
    print(f"  Cost flrs: {COST_FLOOR_V3}")

    grids = build_grids_v3()
    all_instruments = sorted({inst for _, _, cells in grids for inst, _, _ in cells})

    section("Loading instruments")
    bars_map: dict[str, pd.DataFrame] = {}
    for inst in all_instruments:
        df = load_m5(inst)
        if df is not None:
            bars_map[inst] = df
            print(f"  {inst:<8s}: {len(df):>8,} bars  {df.index[0].date()} -> {df.index[-1].date()}")
        else:
            print(f"  {inst:<8s}: SKIPPED (no data)")

    section("Evaluating grids")
    rows = []
    for event_label, gen_fn, cells in grids:
        event_dates = gen_fn(YEARS)
        print(f"\n  [{event_label}] n_events_cal={len(event_dates)}")
        for inst, tz_name, win in cells:
            if inst not in bars_map:
                print(f"    {inst:<8s} SKIPPED (no data)")
                continue
            row = evaluate_grid(event_label, inst, bars_map[inst], event_dates,
                                tz_name, win[0], win[1], win[2], win[3])
            if row is None:
                continue
            row["tz"] = tz_name
            row["window"] = f"{win[0]:02d}:{win[1]:02d}-{win[2]:02d}:{win[3]:02d}"
            row["gap_fill"] = inst in GAP_FILL
            print(f"    {inst:<8s} {tz_name:<13s} {row['window']}  n_ev={row['n_events']:>3d}  "
                  f"ev={row['event_mean_bps']:>+6.2f}  pl={row['placebo_mean_bps']:>+6.2f}  "
                  f"gap={row['null_gap_bps']:>+7.2f}bp  t={row['t_stat']:>+5.2f}  "
                  f"room={row['cost_headroom_bps']:>+6.2f}bp  [{row['tier']}]"
                  f"{'  <<GAP-FILL' if row['gap_fill'] else ''}")
            rows.append(row)

    if not rows:
        print("\n  No rows. Check data loading.")
        return 1

    df = pd.DataFrame(rows)
    order = {"STRONG": 0, "MEDIUM": 1, "WEAK": 2, "REJECT": 3, "INSUFFICIENT_N": 4}
    df_sorted = df.sort_values(
        ["tier", "score"],
        key=lambda c: c.map(order) if c.name == "tier" else -c,
        ascending=[True, True], na_position="last")

    section("Ranked output (all cells)")
    print(df_sorted[["event", "instrument", "window", "n_events", "event_mean_bps",
                     "null_gap_bps", "t_stat", "cost_headroom_bps", "gap_fill", "tier"]]
          .to_string(index=False, float_format=lambda x: f"{x:+.2f}"))

    section("Survivors (STRONG + MEDIUM) — gap-fillers flagged")
    surv = df_sorted[df_sorted["tier"].isin(["STRONG", "MEDIUM"])]
    if len(surv) == 0:
        print("  No STRONG or MEDIUM cells.")
    else:
        print(surv[["event", "instrument", "window", "n_events", "null_gap_bps",
                    "t_stat", "cost_headroom_bps", "gap_fill", "tier"]]
              .to_string(index=False, float_format=lambda x: f"{x:+.2f}"))

    section("Summary")
    tc = df_sorted["tier"].value_counts()
    for tier in ["STRONG", "MEDIUM", "WEAK", "REJECT", "INSUFFICIENT_N"]:
        print(f"  {tier:<16s}: {int(tc.get(tier, 0))}")
    n_gap = int(df_sorted[df_sorted["tier"].isin(["STRONG", "MEDIUM"])]["gap_fill"].sum())
    print(f"  gap-filling survivors: {n_gap}")

    out_csv = os.path.join(_HERE, "structural_flow_audit_v3_results.csv")
    df_sorted.to_csv(out_csv, index=False)
    print(f"\n  Results -> {out_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
