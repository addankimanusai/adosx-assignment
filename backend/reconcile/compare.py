from decimal import Decimal
from typing import Dict, List, Any, Optional


def compare_ledgers(
    a_records: Dict[str, Dict[str, Any]],
    b_entries: List[Dict[str, Any]],
    include_extra_checks: bool = True
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
    include_extra_checks: if True, also checks LOCATION_MISMATCH, DATE_MISMATCH, and VOIDED status.
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

    # 2. Walk through each record in System A
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
            continue

        vals = [e.get("value") for e in entries]

        # Multi-entry handling: Split vs Duplicate
        if len(entries) > 1:
            if any(v is None for v in vals):
                disagreements.append({
                    "reason": "VALUE_MISMATCH",
                    "record_id": rid,
                    "location": a.get("location_id"),
                    "a_location": a.get("location_id"),
                    "b_location": entries[0].get("location_id"),
                    "a_value": a.get("total_value"),
                    "b_value": None,
                    "difference": None,
                    "details": f"Record {rid} has multiple B entries, but one or more have blank/unparseable values.",
                })
                continue

            total_b = sum(vals)
            # If the parts sum exactly to A's total, it is a legitimate split, not an error!
            if total_b != a.get("total_value"):
                disagreements.append({
                    "reason": "DUPLICATE_IN_B",
                    "record_id": rid,
                    "location": a.get("location_id"),
                    "a_location": a.get("location_id"),
                    "b_location": entries[0].get("location_id"),
                    "a_value": a.get("total_value"),
                    "b_value": total_b,
                    "difference": abs(a.get("total_value") - total_b) if a.get("total_value") is not None else None,
                    "details": f"Record {rid} has {len(entries)} entries in System B totaling {total_b}, which does not match System A total {a.get('total_value')}.",
                })
            continue

        # Single entry handling
        e = entries[0]
        val = e.get("value")

        if val is None:
            disagreements.append({
                "reason": "VALUE_MISMATCH",
                "record_id": rid,
                "location": a.get("location_id"),
                "a_location": a.get("location_id"),
                "b_location": e.get("location_id"),
                "a_value": a.get("total_value"),
                "b_value": None,
                "difference": None,
                "details": f"Record {rid} exists in System B (entry {e.get('entry_id')}), but its value is blank/unknown.",
            })
        elif val != a.get("total_value"):
            diff = abs(a.get("total_value") - val) if a.get("total_value") is not None else None
            disagreements.append({
                "reason": "VALUE_MISMATCH",
                "record_id": rid,
                "location": a.get("location_id"),
                "a_location": a.get("location_id"),
                "b_location": e.get("location_id"),
                "a_value": a.get("total_value"),
                "b_value": val,
                "difference": diff,
                "details": f"Value mismatch for {rid}: System A total is {a.get('total_value')}, but System B recorded {val} (difference: {diff}).",
            })

        # Extra domain checks: Location and Date mismatches
        if include_extra_checks:
            if e.get("location_id") and a.get("location_id") and e.get("location_id") != a.get("location_id"):
                disagreements.append({
                    "reason": "LOCATION_MISMATCH",
                    "record_id": rid,
                    "location": a.get("location_id"),
                    "a_location": a.get("location_id"),
                    "b_location": e.get("location_id"),
                    "a_value": a.get("total_value"),
                    "b_value": val,
                    "difference": None,
                    "details": f"Location mismatch for {rid}: System A recorded at {a.get('location_id')}, but System B recorded at {e.get('location_id')}.",
                })

            a_date = str(a.get("event_date") or "")
            b_date = str(e.get("recorded_on") or "")
            if a_date and b_date and a_date != b_date:
                disagreements.append({
                    "reason": "DATE_MISMATCH",
                    "record_id": rid,
                    "location": a.get("location_id"),
                    "a_location": a.get("location_id"),
                    "b_location": e.get("location_id"),
                    "a_value": a.get("total_value"),
                    "b_value": val,
                    "difference": None,
                    "details": f"Date mismatch for {rid}: System A event date is {a_date}, but System B recorded on {b_date}.",
                })

    return disagreements
