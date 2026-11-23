from decimal import Decimal
from typing import Dict, List, Any, Optional


def compare_ledgers(
    a_records: Dict[str, Dict[str, Any]],
    b_entries: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Pure Python reconciliation between System A records and System B entries.

    a_records: dict keyed by record_id:
        {
            "record_id": str,
            "total_value": Decimal,
            "location_id": str,
            "event_date": str or date,
            "state": str
        }
    b_entries: list of dicts:
        {
            "entry_id": str,
            "record_ref": str (cleaned, e.g. "REC-1001"),
            "value": Decimal or None,
            "location_id": str,
            "recorded_on": str or date
        }
    """
    disagreements = []

    # Group B entries by normalized reference
    b_by_ref: Dict[str, List[Dict[str, Any]]] = {}
    for entry in b_entries:
        ref = entry.get("record_ref")
        if ref:
            b_by_ref.setdefault(ref, []).append(entry)

    # 1. MISSING_IN_B: Record exists in System A but has no System B entries
    for rid, a in a_records.items():
        entries = b_by_ref.get(rid, [])
        if not entries:
            disagreements.append({
                "reason": "MISSING_IN_B",
                "record_id": rid,
                "location": a.get("location_id"),
                "a_location": a.get("location_id"),
                "b_location": None,
                "a_value": a.get("total_value"),
                "b_value": None,
                "difference": None,
                "details": f"Record {rid} exists in System A but has no entries in System B.",
            })

    return disagreements
