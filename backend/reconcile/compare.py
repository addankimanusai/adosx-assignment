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

    # 1. ORPHAN_IN_B: Entry exists in System B with reference not in System A
    for ref, entries in b_by_ref.items():
        if ref not in a_records:
            for e in entries:
                disagreements.append({
                    "reason": "ORPHAN_IN_B",
                    "record_id": ref,
                    "location": e.get("location_id"),
                    "a_location": None,
                    "b_location": e.get("location_id"),
                    "a_value": None,
                    "b_value": e.get("value"),
                    "difference": None,
                    "details": f"Entry {e.get('entry_id')} references '{ref}' which does not exist in System A.",
                })

    # 2. MISSING_IN_B: Record exists in System A but has no System B entries
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
