#!/usr/bin/env python3
"""weekly_book_review.py — one-shot weekly live-book review routine.

Chains the four stages of the weekly check-up into a single command and writes
ONE consolidated markdown report. It does not re-implement anything: each stage
shells out to the existing, maintained tool so the sim source can never drift.

    Stage 1  DATA REFRESH   — pull the book's instruments fresh from MT5 and inject
                              into the datalake (scripts/mt5_fetch.py --datalake),
                              backfill any local-CSV→lake gap (datalake_backfill.py
                              --apply), then print a /catalog coverage table so a
                              stale feed can't masquerade as "nothing fired".
    Stage 2  SIM THE WEEK   — what the book SHOULD have run this week: entry times,
                              deployed sizing, exits, per-leg + book P&L.
                              (experiments/book_review/book_period.py --fast)
    Stage 3  ACTUAL + RECONCILE — pull realized MT5 fills for the same window and
                              reconcile them leg-by-leg against the sim
                              (book_period.py --fast --live → ✓ match / ⚠ SIM-ONLY /
                              ⚠ LIVE-ONLY / in-flight).
    Stage 4  REALIZED HEALTH — cumulative deploy-to-date realized metrics + Gate-1
                              scoring (scripts/book_checkup.py).

Stages 2 and 3 are produced by a SINGLE `book_period.py --fast --live` invocation
(its output already separates the sim view in sections 2-3 from the live reconcile
in section 5); we split that output into the report's two sections.

Prereq for live stages (3, 4) and the data fetch (1): the local MT5 terminal open
and logged into the Eightcap account that holds the live EAs. If MT5 is
unavailable, those stages degrade gracefully (the sim in stage 2 runs off the
on-disk CSVs regardless) and the report says so — it never aborts the whole run.

Usage:
    venv\\Scripts\\python.exe scripts\\weekly_book_review.py
        # current ISO week (Mon 00:00 UTC → now), full routine, fresh fetch

    venv\\Scripts\\python.exe scripts\\weekly_book_review.py --last 14
    venv\\Scripts\\python.exe scripts\\weekly_book_review.py --start 2026-06-01 --end 2026-06-05
    venv\\Scripts\\python.exe scripts\\weekly_book_review.py --skip-fetch   # reuse on-disk bars
    venv\\Scripts\\python.exe scripts\\weekly_book_review.py --no-live      # sim only, no MT5

Report: live_data/weekly/<YYYY-MM-DD>.md  (live_data/ is gitignored — private).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PY = sys.executable  # the venv interpreter this script is run with
WEEKLY_DIR = _ROOT / "live_data" / "weekly"

# The Windows console defaults to cp1252, which can't encode the ✓/⚠/→ glyphs the
# sub-tools (and this script) emit. Force UTF-8 so a live console print never dies.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

# The book's instruments and the timeframes its legs consume. M5 is the working
# TF for the intraday/structural legs; H1 backs xau_session and is cheap for the
# rest. Fetching the full grid just widens the lake — that's the point.
#   GER40   → orb_dax
#   NDX100  → lunch_fade, ndx_trend_day, event_calendar, global_settlement_short
#   XAUUSD  → xau_session, quarter_end_xau_short
#   SPX500  → holiday_calendar, global_settlement_short
#   UK100   → global_settlement_short
#   JPN225  → global_settlement_short (JPN SQ leg)
#   USDJPY  → pre_boj_drift (watchlist leg)
BOOK_SYMBOLS = ["GER40", "NDX100", "XAUUSD", "SPX500", "UK100", "JPN225", "USDJPY"]
BOOK_TIMEFRAMES = ["M5", "H1"]
# How far back to re-pull on each refresh. mt5_fetch MERGES into the existing CSV,
# so a short trailing window is enough to top up recent bars + inject the lake gap;
# we don't need to re-pull years of history every week. Env-overridable.
FETCH_LOOKBACK_DAYS = int(os.getenv("WEEKLY_FETCH_LOOKBACK_DAYS", "60"))


def _run(cmd: list[str], *, label: str, timeout: int = 1200) -> tuple[int, str]:
    """Run a subprocess, echo its output live to the console, and capture it.

    Returns (returncode, combined_output). Never raises on a non-zero exit — a
    failed stage is reported in-band so the routine continues to the next stage.
    """
    print(f"\n{'#' * 96}\n# {label}\n# $ {' '.join(cmd)}\n{'#' * 96}", flush=True)
    # Force UTF-8 in the child so its own ✓/⚠/→ prints don't crash on a piped
    # (non-console) stdout, which otherwise falls back to cp1252 on Windows.
    child_env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    try:
        proc = subprocess.run(
            cmd, cwd=str(_ROOT), text=True, capture_output=True, timeout=timeout,
            encoding="utf-8", errors="replace", env=child_env,
        )
    except subprocess.TimeoutExpired:
        msg = f"[TIMEOUT after {timeout}s]"
        print(msg)
        return 124, msg
    except Exception as e:  # noqa: BLE001 — surface, don't crash the routine
        msg = f"[FAILED to launch: {type(e).__name__}: {e}]"
        print(msg)
        return 1, msg
    out = (proc.stdout or "") + (proc.stderr or "")
    print(out, flush=True)
    return proc.returncode, out


def _clip_lines(text: str, width: int = 220) -> str:
    """Clip over-long captured lines for the markdown report. A down lake makes
    mt5_fetch emit the same ~600-char DuckDB error on every ingest line; clipping
    keeps the signal (which symbol failed, the error head) without 14 identical
    blobs. The live console (above) still showed the full untruncated output."""
    return "\n".join(
        (ln[:width] + " …[clipped]") if len(ln) > width else ln
        for ln in text.splitlines()
    )


# --------------------------------------------------------------------------- #
# Stage 1 — data refresh                                                        #
# --------------------------------------------------------------------------- #
def stage_fetch() -> str:
    """Refresh the book's instruments from MT5 into the datalake + backfill gaps."""
    since = (datetime.now(timezone.utc) - timedelta(days=FETCH_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    parts: list[str] = []

    rc, out = _run(
        [
            _PY, str(_ROOT / "scripts" / "mt5_fetch.py"),
            "--symbols", ",".join(BOOK_SYMBOLS),
            "--timeframes", ",".join(BOOK_TIMEFRAMES),
            "--from", since,
            "--datalake",
        ],
        label=f"STAGE 1a — MT5 fetch + datalake inject  (since {since})",
    )
    parts.append(f"### 1a. MT5 fetch → datalake (since {since})\n\n```\n{_clip_lines(out).strip()}\n```")
    if rc != 0:
        parts.append(
            "\n> ⚠ mt5_fetch exited non-zero — likely the MT5 terminal isn't open/"
            "logged in. The sim below still runs off whatever bars are already on disk, "
            "but they may be stale (see the coverage table)."
        )

    # Scope the backfill to the book's stems only — a bare `--apply` walks all
    # ~437 CSVs in ohlc_data/, which is scope creep for a weekly BOOK review (and
    # the slow part most exposed to lake flakiness). Stage 1a already injected
    # these fresh from MT5, so this is a near-instant idempotent catch-up; lake-
    # wide backfilling is a separate manual concern.
    book_stems = ",".join(f"{s}_{tf}" for s in BOOK_SYMBOLS for tf in BOOK_TIMEFRAMES)
    rc, out = _run(
        [_PY, str(_ROOT / "scripts" / "datalake_backfill.py"), "--apply", "--only", book_stems],
        label="STAGE 1b — backfill book CSV → lake gaps (book stems only)",
    )
    parts.append(f"\n### 1b. datalake backfill (book stems, CSV → lake)\n\n```\n{_clip_lines(out).strip()}\n```")

    parts.append("\n### 1c. Lake coverage (max_date per book instrument)\n\n" + _coverage_table())
    return "\n".join(parts)


def _coverage_table() -> str:
    """Query /catalog and tabulate max_date per (book instrument, tf). Best-effort:
    a lake hiccup degrades to a one-line note rather than failing the routine."""
    try:
        sys.path.insert(0, str(_ROOT))
        from data import get_client  # noqa: PLC0415 — lazy: keep the lake import optional

        client = get_client()
        today = datetime.now(timezone.utc).date()
        lines = ["```", f"{'instrument':<10} {'tf':<4} {'max_date':<22} {'records':>10}  fresh?", "-" * 60]
        for sym in BOOK_SYMBOLS:
            for tf in BOOK_TIMEFRAMES:
                cov = client.coverage(sym, tf)
                if not cov:
                    lines.append(f"{sym:<10} {tf:<4} {'(not catalogued)':<22} {'-':>10}")
                    continue
                maxd = str(cov.get("max_date") or "?")
                rec = cov.get("record_count")
                fresh = ""
                try:
                    md = datetime.fromisoformat(maxd.replace("Z", "+00:00")).date()
                    fresh = "" if (today - md).days <= 4 else f"  <-- {((today - md).days)}d stale"
                except Exception:  # noqa: BLE001
                    pass
                lines.append(f"{sym:<10} {tf:<4} {maxd:<22} {str(rec):>10}{fresh}")
        lines.append("```")
        return "\n".join(lines)
    except Exception as e:  # noqa: BLE001
        return f"> coverage lookup unavailable ({type(e).__name__}: {e})"


# --------------------------------------------------------------------------- #
# Stage 2 + 3 — sim the week, then reconcile against live                       #
# --------------------------------------------------------------------------- #
def stage_book_period(window_args: list[str], live: bool, fast: bool) -> tuple[str, str]:
    """Run book_period once (with --live if requested) and split its output into
    the SIM section (everything up to the live block) and the LIVE/RECONCILE
    section (from '5. LIVE FILLS' on). Returns (sim_md, live_md)."""
    cmd = [_PY, str(_ROOT / "experiments" / "book_review" / "book_period.py")] + window_args
    if fast:
        cmd.append("--fast")
    if live:
        cmd.append("--live")
    _, out = _run(cmd, label=f"STAGE 2+3 — book sim{' + live reconcile' if live else ''} for the window")

    marker = "5. LIVE FILLS"
    if live and marker in out:
        idx = out.index(marker)
        # back up to the banner line ('=====') that precedes the section header
        head = out.rfind("\n" + "=" * 10, 0, idx)
        cut = head if head != -1 else idx
        sim_md = out[:cut].strip()
        live_md = out[cut:].strip()
    else:
        sim_md = out.strip()
        live_md = "(live reconciliation not run — pass --live with the MT5 terminal open)"
    return (
        f"```\n{sim_md}\n```",
        f"```\n{live_md}\n```",
    )


# --------------------------------------------------------------------------- #
# Stage 3.5 — trade-level sim↔live reconciliation                               #
# --------------------------------------------------------------------------- #
def stage_trade_level(window_args: list[str]) -> str:
    """Per-trade join (entry/exit ts, price, return) below the count-level Stage 3.
    Flags fill slippage on matched trades and existence gaps (SIM-ONLY / LIVE-ONLY).
    Needs the MT5 terminal open; degrades to a note if the live pull fails."""
    cmd = [_PY, str(_ROOT / "experiments" / "book_review" / "trade_level_reconcile.py")] + window_args
    rc, out = _run(cmd, label="STAGE 3.5 — trade-level sim↔live reconcile")
    return f"```\n{_clip_lines(out).strip()}\n```"


# --------------------------------------------------------------------------- #
# Stage 4 — cumulative realized health                                          #
# --------------------------------------------------------------------------- #
def stage_checkup(since: str) -> str:
    rc, out = _run(
        [_PY, str(_ROOT / "scripts" / "book_checkup.py"), "--since", since, "--no-plot"],
        label=f"STAGE 4 — realized metrics + Gate-1 (deploy→now, since {since})",
    )
    note = ""
    if rc != 0:
        note = ("\n> ⚠ book_checkup exited non-zero — MT5 terminal likely not "
                "open/logged in; realized metrics unavailable this run.")
    return f"```\n{out.strip()}\n```{note}"


# --------------------------------------------------------------------------- #
def _resolve_window(args) -> tuple[str, str, list[str]]:
    """Return (win_start_iso, win_end_iso, book_period_window_args)."""
    today = datetime.now(timezone.utc).date()
    if args.last:
        win0, win1 = today - timedelta(days=args.last), today
        return win0.isoformat(), win1.isoformat(), ["--last", str(args.last)]
    win1 = datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else today
    win0 = (datetime.strptime(args.start, "%Y-%m-%d").date() if args.start
            else win1 - timedelta(days=win1.weekday()))
    wargs = []
    if args.start:
        wargs += ["--start", args.start]
    if args.end:
        wargs += ["--end", args.end]
    return win0.isoformat(), win1.isoformat(), wargs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", help="window start YYYY-MM-DD (default: Monday of current ISO week)")
    ap.add_argument("--end", help="window end YYYY-MM-DD inclusive (default: today UTC)")
    ap.add_argument("--last", type=int, help="rolling window of N days ending today (overrides --start/--end)")
    ap.add_argument("--skip-fetch", action="store_true", help="skip stage 1; use the bars already on disk")
    ap.add_argument("--no-live", action="store_true", help="skip the live MT5 pull (stages 3 reconcile + 4)")
    ap.add_argument("--full", action="store_true",
                    help="drop --fast on the sim (full 2018→now run for the absolute $ equity anchor; ~4x slower)")
    ap.add_argument("--checkup-since", default="2026-04-22",
                    help="earliest deal date for stage-4 realized metrics (default: orb_dax deploy 2026-04-22)")
    args = ap.parse_args()

    win0, win1, window_args = _resolve_window(args)
    live = not args.no_live
    started = datetime.now(timezone.utc)

    print(f"\n{'=' * 96}\n  WEEKLY BOOK REVIEW   {win0} → {win1}   "
          f"(fetch={'off' if args.skip_fetch else 'on'}, live={'on' if live else 'off'}, "
          f"fast={'off' if args.full else 'on'})\n{'=' * 96}")

    sections: dict[str, str] = {}

    if args.skip_fetch:
        sections["fetch"] = "_(skipped: --skip-fetch — review ran on the bars already on disk)_"
    else:
        sections["fetch"] = stage_fetch()

    sim_md, live_md = stage_book_period(window_args, live=live, fast=not args.full)
    sections["sim"] = sim_md
    sections["live"] = live_md

    sections["trade_level"] = (
        "_(skipped: --no-live)_" if not live else stage_trade_level(window_args)
    )
    sections["checkup"] = (
        "_(skipped: --no-live)_" if not live else stage_checkup(args.checkup_since)
    )

    # ---- consolidated report ----------------------------------------------
    WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
    report_path = WEEKLY_DIR / f"{started.strftime('%Y-%m-%d')}.md"
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    report = f"""# Weekly book review — {win0} → {win1}

_Generated {started.strftime('%Y-%m-%d %H:%M UTC')} by `scripts/weekly_book_review.py` in {elapsed:.0f}s._
_Window: {win0} → {win1}. Fetch: {'skipped' if args.skip_fetch else 'on'}. Live: {'on' if live else 'off'}. Sim mode: {'full (since-2023 $ anchor)' if args.full else 'fast (window+120d warmup)'}._

> **How to read this.** Stage 2 is what the book *should* have run (deployed sizing,
> entry/exit times, per-leg + book P&L). Stage 3 reconciles that against the *actual*
> MT5 fills — chase any `⚠ SIM-ONLY` (EA failed to fire) or `⚠ LIVE-ONLY`. Stage 4 is
> the cumulative deploy-to-date realized picture, not the week's.

---

## Stage 1 — Data refresh (instruments → datalake)

{sections['fetch']}

---

## Stage 2 — Simulation: what the book should have run this week

{sections['sim']}

---

## Stage 3 — Actual MT5 fills + reconciliation vs sim

{sections['live']}

---

## Stage 3.5 — Trade-level sim↔live reconcile (fills, prices, returns)

{sections['trade_level']}

---

## Stage 4 — Cumulative realized health + Gate-1 (deploy → now)

{sections['checkup']}
"""
    report_path.write_text(report, encoding="utf-8")
    print(f"\n{'=' * 96}\n  Report written: {report_path.relative_to(_ROOT)}   ({elapsed:.0f}s)\n{'=' * 96}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
