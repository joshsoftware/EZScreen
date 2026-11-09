#!/usr/bin/env python3
"""Rebuild screening scores and written summaries with the current weights.

Question scores stay as they were saved. Category totals, the overall score,
and the written final summary are rebuilt with Must-have 60, Domain 20,
Good to have 10, and Skill gaps 10.

The first run keeps the previous summary at
analysis_result.final_summary_before_reweight.

From the repo root, dry-run (prints old and new scores, writes nothing):

  docker compose run --rm \
    -v "$(pwd)/services/ai-core-services:/app" \
    ai-core-services \
    python scripts/reweight_screening_summaries.py

Write the results:

  docker compose run --rm \
    -v "$(pwd)/services/ai-core-services:/app" \
    ai-core-services \
    python scripts/reweight_screening_summaries.py --apply

One interview:

  python scripts/reweight_screening_summaries.py --session-id <uuid> --apply
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, text  # noqa: E402

from src.core.config import settings  # noqa: E402
from src.llm.client import OllamaClient  # noqa: E402
from src.screening_pipeline.persistence import build_final_summary  # noqa: E402
from src.screening_pipeline.routing_engine import calculate_final_weighted_score  # noqa: E402

SUMMARY_FAILED = "failed to generate qualitative summary"


def _ended_in_silence(metadata: object) -> bool:
    if not isinstance(metadata, dict):
        return False
    transcript = metadata.get("conversation_transcript")
    if not isinstance(transcript, list):
        return False
    return any(
        isinstance(item, dict) and item.get("interaction_type") == "silence_prompt"
        for item in transcript
    )


def _evaluations(analysis_result: object) -> list[dict]:
    if not isinstance(analysis_result, dict):
        return []
    evaluations = analysis_result.get("evaluations")
    if not isinstance(evaluations, list):
        return []
    return [item for item in evaluations if isinstance(item, dict)]


def _load_rows(engine, session_id: str | None) -> list[dict]:
    query = """
        SELECT a.id::text AS id,
               a.interview_session_id::text AS interview_session_id,
               a.analysis_result AS analysis_result,
               s.interview_metadata AS interview_metadata
        FROM interview_analysis a
        LEFT JOIN interview_session s ON s.id = a.interview_session_id
        WHERE a.analysis_result IS NOT NULL
    """
    params: dict[str, str] = {}
    if session_id:
        query += " AND a.interview_session_id = CAST(:session_id AS uuid)"
        params["session_id"] = session_id
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(text(query), params).mappings()]


def _save_summary(engine, analysis_id: str, summary: dict) -> None:
    with engine.begin() as conn:
        current = conn.execute(
            text(
                """
                SELECT analysis_result
                FROM interview_analysis
                WHERE id = CAST(:id AS uuid)
                FOR UPDATE
                """
            ),
            {"id": analysis_id},
        ).scalar_one()
        if not isinstance(current, dict):
            raise RuntimeError(f"{analysis_id} has no analysis_result object")
        updated = dict(current)
        previous = updated.get("final_summary")
        if "final_summary_before_reweight" not in updated and isinstance(previous, dict):
            updated["final_summary_before_reweight"] = previous
        updated["final_summary"] = summary
        conn.execute(
            text(
                """
                UPDATE interview_analysis
                SET analysis_result = CAST(:payload AS jsonb)
                WHERE id = CAST(:id AS uuid)
                """
            ),
            {"id": analysis_id, "payload": json.dumps(updated)},
        )


async def _rebuild(engine, row: dict, llm_client: OllamaClient, apply: bool) -> str:
    evaluations = _evaluations(row["analysis_result"])
    if not evaluations:
        return "skip (no evaluated answers)"

    math = calculate_final_weighted_score(evaluations)
    previous = row["analysis_result"].get("final_summary") if isinstance(row["analysis_result"], dict) else None
    old_overall = previous.get("overall_score") if isinstance(previous, dict) else None
    new_overall = math["overall_score"]
    line = f"{old_overall} -> {new_overall}  raw {math['total_raw_score']}"

    if not apply:
        return f"dry-run {line}"

    reason = "candidate_silence" if _ended_in_silence(row["interview_metadata"]) else "re_evaluation"
    summary = await build_final_summary(llm_client, evaluations, termination_reason=reason)
    if SUMMARY_FAILED in str(summary.get("final_recommendation") or ""):
        return f"failed {line} (summary was not written)"

    _save_summary(engine, row["id"], summary)
    return f"updated {line}"


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the new scores and summaries. Without this, only print the new scores.",
    )
    parser.add_argument("--session-id", help="Recalculate one interview_session id.")
    args = parser.parse_args()

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    rows = _load_rows(engine, args.session_id)
    llm_client = OllamaClient()

    updated = previewed = skipped = failed = 0
    for row in rows:
        try:
            status = await _rebuild(engine, row, llm_client, args.apply)
        except Exception as exc:
            failed += 1
            print(f"{row['interview_session_id']}  error  {exc}")
            continue
        if status.startswith("updated"):
            updated += 1
        elif status.startswith("dry-run"):
            previewed += 1
        elif status.startswith("failed"):
            failed += 1
        else:
            skipped += 1
        print(f"{row['interview_session_id']}  {status}")

    print(
        f"done  rows={len(rows)}  updated={updated}  "
        f"previewed={previewed}  skipped={skipped}  failed={failed}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
