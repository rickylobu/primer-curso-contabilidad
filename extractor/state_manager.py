"""
state_manager.py
Tracks extraction progress to enable idempotent retries and seamless resume.

Status lifecycle:
    PENDING → IN_PROGRESS → DONE          (happy path)
                          → SUSPECT_BLANK  (empty response, queued for second pass)
                          → CONFIRMED_BLANK (verified empty after second pass)
                          → FAILED         (API error after max retries)

Each OCR attempt gets a unique attempt_id (UUID4) so requests are always
distinguishable — important for tracing, deduplication, and future async work.
"""

import json
import time
import uuid
from pathlib import Path
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Optional


class PageStatus(str, Enum):
    PENDING          = "pending"
    IN_PROGRESS      = "in_progress"
    DONE             = "done"
    SUSPECT_BLANK    = "suspect_blank"    # empty response — queued for 2nd pass
    CONFIRMED_BLANK  = "confirmed_blank"  # verified empty after hi-res retry
    FAILED           = "failed"
    SKIPPED          = "skipped"          # skip_existing=true, file already existed


@dataclass
class PageState:
    page_number:      int
    status:           PageStatus = PageStatus.PENDING
    attempts:         int = 0
    last_attempt_id:  Optional[str] = None   # UUID4 of the last OCR call
    last_attempt_at:  Optional[str] = None
    error_message:    Optional[str] = None
    output_file:      Optional[str] = None
    tokens_used:      Optional[int] = None
    blank_retries:    int = 0                # times retried specifically for blank check


@dataclass
class ExtractionState:
    pdf_filename:    str
    total_pages:     int
    started_at:      str
    last_updated_at: str
    pages:           dict = field(default_factory=dict)

    @property
    def done_count(self) -> int:
        return sum(
            1 for p in self.pages.values()
            if p["status"] in (PageStatus.DONE, PageStatus.SKIPPED,
                               PageStatus.CONFIRMED_BLANK)
        )

    @property
    def suspect_blank_pages(self) -> list:
        return [int(k) for k, v in self.pages.items()
                if v["status"] == PageStatus.SUSPECT_BLANK]

    @property
    def failed_pages(self) -> list:
        return [int(k) for k, v in self.pages.items()
                if v["status"] == PageStatus.FAILED]

    @property
    def pending_pages(self) -> list:
        return [int(k) for k, v in self.pages.items()
                if v["status"] in (PageStatus.PENDING, PageStatus.IN_PROGRESS)]


STATE_FILE = Path("output") / ".extraction_state.json"


class StateManager:
    """
    Manages extraction state with atomic writes.
    Guarantees idempotency: DONE/CONFIRMED_BLANK pages are never reprocessed.
    Each OCR attempt is assigned a unique attempt_id for full traceability.
    """

    def __init__(self, pdf_filename: str, total_pages: int):
        self.pdf_filename = pdf_filename
        self.total_pages  = total_pages
        self.state_file   = STATE_FILE
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state: ExtractionState = self._load_or_create()

    # ── Persistence ────────────────────────────────────────────────────────

    def _load_or_create(self) -> ExtractionState:
        if self.state_file.exists():
            try:
                content = self.state_file.read_text(encoding="utf-8").strip()
                raw = json.loads(content) if content else {}
            except (json.JSONDecodeError, OSError):
                print("  ⚠️   State file was corrupt. Starting fresh.")
                raw = {}

            if raw.get("pdf_filename") == self.pdf_filename:
                state = ExtractionState(
                    pdf_filename    = raw["pdf_filename"],
                    total_pages     = raw["total_pages"],
                    started_at      = raw["started_at"],
                    last_updated_at = raw["last_updated_at"],
                    pages           = raw["pages"],
                )
                done    = state.done_count
                suspect = len(state.suspect_blank_pages)
                failed  = len(state.failed_pages)
                print(
                    f"  ♻️   Resuming: "
                    f"{done} done  |  {suspect} suspect-blank  |  "
                    f"{failed} failed  (of {state.total_pages} total)"
                )
                return state
            else:
                print("  ⚠️   State file found for a different PDF. Starting fresh.")

        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        state = ExtractionState(
            pdf_filename    = self.pdf_filename,
            total_pages     = self.total_pages,
            started_at      = now,
            last_updated_at = now,
            pages           = {
                str(i): asdict(PageState(page_number=i))
                for i in range(1, self.total_pages + 1)
            },
        )
        self._persist(state)
        return state

    def _persist(self, state=None) -> None:
        s = state or self._state
        s.last_updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(s), indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.state_file)

    # ── Attempt ID ─────────────────────────────────────────────────────────

    @staticmethod
    def new_attempt_id() -> str:
        return str(uuid.uuid4())

    # ── Page lifecycle ──────────────────────────────────────────────────────

    def is_terminal(self, page_number: int) -> bool:
        entry = self._state.pages.get(str(page_number), {})
        return entry.get("status") in (
            PageStatus.DONE, PageStatus.SKIPPED, PageStatus.CONFIRMED_BLANK
        )

    def is_done(self, page_number: int) -> bool:
        return self.is_terminal(page_number)

    def mark_in_progress(self, page_number: int) -> str:
        attempt_id = self.new_attempt_id()
        entry = self._state.pages[str(page_number)]
        entry["status"]          = PageStatus.IN_PROGRESS
        entry["attempts"]        = entry.get("attempts", 0) + 1
        entry["last_attempt_id"] = attempt_id
        entry["last_attempt_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._persist()
        return attempt_id

    def mark_done(self, page_number: int, output_file: str, tokens_used: int = 0) -> None:
        entry = self._state.pages[str(page_number)]
        entry["status"]        = PageStatus.DONE
        entry["output_file"]   = output_file
        entry["tokens_used"]   = tokens_used
        entry["error_message"] = None
        self._persist()

    def mark_skipped(self, page_number: int, output_file: str) -> None:
        entry = self._state.pages[str(page_number)]
        entry["status"]      = PageStatus.SKIPPED
        entry["output_file"] = output_file
        self._persist()

    def mark_suspect_blank(self, page_number: int, output_file: str, tokens_used: int = 0) -> None:
        entry = self._state.pages[str(page_number)]
        entry["status"]      = PageStatus.SUSPECT_BLANK
        entry["output_file"] = output_file
        entry["tokens_used"] = tokens_used
        self._persist()

    def mark_confirmed_blank(self, page_number: int, output_file: str) -> None:
        entry = self._state.pages[str(page_number)]
        entry["status"]        = PageStatus.CONFIRMED_BLANK
        entry["output_file"]   = output_file
        entry["blank_retries"] = entry.get("blank_retries", 0) + 1
        self._persist()

    def mark_blank_retry_in_progress(self, page_number: int) -> str:
        attempt_id = self.new_attempt_id()
        entry = self._state.pages[str(page_number)]
        entry["status"]          = PageStatus.IN_PROGRESS
        entry["blank_retries"]   = entry.get("blank_retries", 0) + 1
        entry["last_attempt_id"] = attempt_id
        entry["last_attempt_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._persist()
        return attempt_id

    def mark_failed(self, page_number: int, error: str) -> None:
        entry = self._state.pages[str(page_number)]
        entry["status"]        = PageStatus.FAILED
        entry["error_message"] = error
        self._persist()

    def get_attempts(self, page_number: int) -> int:
        return self._state.pages.get(str(page_number), {}).get("attempts", 0)

    def get_suspect_blank_queue(self) -> list:
        return sorted(self._state.suspect_blank_pages)

    def get_failed_queue(self) -> list:
        return sorted(self._state.failed_pages)

    def summary(self) -> dict:
        counts = {s.value: 0 for s in PageStatus}
        total_tokens = 0
        for entry in self._state.pages.values():
            counts[entry["status"]] += 1
            total_tokens += entry.get("tokens_used") or 0
        return {
            "total":             self._state.total_pages,
            "done":              counts[PageStatus.DONE],
            "skipped":           counts[PageStatus.SKIPPED],
            "confirmed_blank":   counts[PageStatus.CONFIRMED_BLANK],
            "suspect_blank":     counts[PageStatus.SUSPECT_BLANK],
            "failed":            counts[PageStatus.FAILED],
            "pending":           counts[PageStatus.PENDING],
            "total_tokens_used": total_tokens,
            "started_at":        self._state.started_at,
            "last_updated_at":   self._state.last_updated_at,
        }
