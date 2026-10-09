"""Read-only access to persisted single-point measurement results."""
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from lab_auto.api.models import HistoryDetail, HistoryRecord
from lab_auto.api.paths import measurement_root
from lab_auto.workflow.raman import read_single_point_result

router = APIRouter(prefix="/api/history", tags=["history"])
_FILES = ("raw.csv", "corrected.csv", "background.csv", "metadata.json", "run.log")


def _record_dir(record_id: str) -> Path:
    root = measurement_root()
    try:
        candidate = (root / record_id).resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid history record") from exc
    if candidate.parent != root or not candidate.is_dir():
        raise HTTPException(status_code=404, detail="History record not found")
    return candidate


def _read_record(run_dir: Path) -> HistoryRecord | None:
    try:
        if run_dir.resolve().parent != measurement_root():
            return None
        metadata_path = run_dir / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("status") == "running":
            return None  # not yet committed; interrupted API jobs are listed separately
        timestamp = metadata.get("timestamp") or datetime.fromtimestamp(
            metadata_path.stat().st_mtime,
            tz=timezone.utc,
        ).isoformat()
        warnings = metadata.get("warnings")
        return HistoryRecord(
            id=run_dir.name,
            created_at=str(timestamp),
            completed_at=metadata.get("completed_at") or str(timestamp),
            status=metadata.get("status", "completed"),
            error="; ".join(str(error) for error in metadata.get("errors", [])) or None,
            sample_id=metadata.get("sample_id"),
            operator=metadata.get("operator"),
            mode=str(metadata.get("runtime_mode") or "unknown"),
            warnings_count=len(warnings) if isinstance(warnings, list) else 0,
            files=[name for name in _FILES if (run_dir / name).is_file()],
        )
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        return None


@router.get("", response_model=list[HistoryRecord])
async def list_history():
    """List valid persisted runs, newest first."""
    root = measurement_root()
    if not root.is_dir():
        return []
    records = [record for path in root.iterdir() if path.is_dir() if (record := _read_record(path))]
    return sorted(records, key=lambda record: record.created_at, reverse=True)


@router.get("/{record_id}", response_model=HistoryDetail)
async def get_history(record_id: str):
    """Return one chart-ready persisted measurement."""
    run_dir = _record_dir(record_id)
    record = _read_record(run_dir)
    if record is None:
        raise HTTPException(status_code=422, detail="History record is invalid")
    try:
        result = {
            "output_directory": str(run_dir),
            "mode": record.mode,
            **read_single_point_result(run_dir),
        }
    except (OSError, UnicodeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="Measurement files are invalid") from exc
    return HistoryDetail(record=record, result=result)


@router.get("/{record_id}/files/{filename}", response_class=FileResponse)
async def download_history_file(record_id: str, filename: str):
    """Download one known output file from one server-owned run directory."""
    if filename not in _FILES:
        raise HTTPException(status_code=404, detail="File not found")
    path = _record_dir(record_id) / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=filename)
