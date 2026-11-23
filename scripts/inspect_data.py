"""
Data inspection script to count rows, blanks, odd formats, duplicates, and discrepancies.
Run before and after data imports to ensure zero data loss.
"""
import csv
import re
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation

def normalize_ref(raw):
    m = re.search(r"\d+", raw or "")
    return f"REC-{m.group()}" if m else None

def parse_amount(raw):
    s = (raw or "").strip().replace(",", "")
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None

def inspect():
    print("=" * 60)
    print("DATA AUDIT & ANOMALY REPORT")
    print("=" * 60)

    # 1. Locations
    with open("backend/data/locations.csv", encoding="utf-8") as f:
        loc_rows = list(csv.DictReader(f))
    print(f"\n[locations.csv] Total rows: {len(loc_rows)}")
    loc_to_org = {}
    for r in loc_rows:
        loc_to_org[r["location_id"].strip()] = r["org_id"].strip()
        print(f"  {r['location_id']}: {r['org_id']} ({r.get('location_name', '')})")

    # 2. System A
    with open("backend/data/system_a.csv", encoding="utf-8") as f:
        a_rows = list(csv.DictReader(f))
    print(f"\n[system_a.csv] Total rows: {len(a_rows)}")
    a_dict = {}
    blank_actor_count = 0
    voided_count = 0
    a_loc_counts = Counter()

    for r in a_rows:
        rid = r["record_id"].strip()
        a_dict[rid] = r
        a_loc_counts[r["location_id"].strip()] += 1
        if not (r.get("actor_id") or "").strip():
            blank_actor_count += 1
            print(f"  System A blank actor_id at record: {rid}")
        if r.get("state", "").strip() == "VOIDED":
            voided_count += 1
            print(f"  System A VOIDED record: {rid}")

    print(f"  System A location breakdown: {dict(a_loc_counts)}")
    print(f"  System A blank actor_ids: {blank_actor_count}")
    print(f"  System A voided records: {voided_count}")

    # 3. System B
    with open("backend/data/system_b.csv", encoding="utf-8") as f:
        b_rows = list(csv.DictReader(f))
    print(f"\n[system_b.csv] Total rows: {len(b_rows)}")

    b_loc_counts = Counter()
    odd_refs = []
    blank_values = []
    formatted_values = []
    b_by_ref = defaultdict(list)

    for r in b_rows:
        eid = r["entry_id"].strip()
        raw_ref = r["record_ref"]
        cleaned_ref = normalize_ref(raw_ref)
        raw_val = r["value"]
        parsed_val = parse_amount(raw_val)
        loc = r["location_id"].strip()
        b_loc_counts[loc] += 1

        b_by_ref[cleaned_ref].append((r, parsed_val))

        # Check ref formats
        if not re.match(r"^REC-\d+$", raw_ref.strip()):
            odd_refs.append((eid, raw_ref, cleaned_ref))

        # Check value formats
        stripped_val = (raw_val or "").strip()
        if not stripped_val:
            blank_values.append((eid, raw_ref))
        elif "," in stripped_val:
            formatted_values.append((eid, raw_val, parsed_val))

    print(f"  System B location breakdown: {dict(b_loc_counts)}")
    print(f"  Odd reference formats ({len(odd_refs)}):")
    for eid, raw, cleaned in odd_refs:
        print(f"    {eid}: raw='{raw}' -> cleaned='{cleaned}'")
    print(f"  Blank values ({len(blank_values)}):")
    for eid, raw in blank_values:
        print(f"    {eid}: ref='{raw}' (stored as null, NOT zero)")
    print(f"  Non-standard formatted values ({len(formatted_values)}):")
    for eid, raw, parsed in formatted_values:
        print(f"    {eid}: raw='{raw}' -> parsed={parsed}")

    # 4. Cross comparison
    print("\n[Cross-Ledger Discrepancies]")
    # Missing in B
    missing_in_b = [rid for rid in a_dict if rid not in b_by_ref]
    print(f"  Missing in B ({len(missing_in_b)}):")
    for rid in missing_in_b:
        print(f"    {rid} (Org: {loc_to_org.get(a_dict[rid]['location_id'].strip())})")

    # Orphans in B
    orphans_in_b = [ref for ref in b_by_ref if ref not in a_dict]
    print(f"  Orphans in B ({len(orphans_in_b)}):")
    for ref in orphans_in_b:
        for r, _ in b_by_ref[ref]:
            print(f"    Entry {r['entry_id']} -> ref {r['record_ref']} (cleaned: {ref}), Loc: {r['location_id']} (Org: {loc_to_org.get(r['location_id'].strip())})")

    # Multi-entry
    print("  Multiple B entries for single A record:")
    for ref, entries in b_by_ref.items():
        if ref in a_dict and len(entries) > 1:
            a_tot = Decimal(a_dict[ref]["total_value"].strip())
            vals = [val for _, val in entries]
            is_split = all(v is not None for v in vals) and sum(vals) == a_tot
            print(f"    {ref}: count={len(entries)}, vals={vals}, sum={sum(vals) if all(v is not None for v in vals) else None}, A_total={a_tot} -> {'VALID SPLIT (Not error)' if is_split else 'DUPLICATE_IN_B'}")

    # Value mismatches
    print("  Value mismatches (single entry):")
    for ref, entries in b_by_ref.items():
        if ref in a_dict and len(entries) == 1:
            r, b_val = entries[0]
            a_tot = Decimal(a_dict[ref]["total_value"].strip())
            if b_val is None or b_val != a_tot:
                print(f"    {ref}: B_val={b_val} (raw: '{r['value']}'), A_total={a_tot}, A_base={a_dict[ref]['base_value']}")

    # Location mismatches
    print("  Cross-location differences:")
    for ref, entries in b_by_ref.items():
        if ref in a_dict:
            a_loc = a_dict[ref]["location_id"].strip()
            for r, _ in entries:
                b_loc = r["location_id"].strip()
                if a_loc != b_loc:
                    print(f"    {ref}: System A={a_loc} ({loc_to_org.get(a_loc)}), System B={b_loc} ({loc_to_org.get(b_loc)}) [CROSS-TENANT TRAP]")

    # Date mismatches
    print("  Date differences:")
    for ref, entries in b_by_ref.items():
        if ref in a_dict:
            a_date = a_dict[ref]["event_date"].strip()
            for r, _ in entries:
                b_date = r["recorded_on"].strip()
                if a_date != b_date:
                    print(f"    {ref}: System A date={a_date}, System B date={b_date}")

if __name__ == "__main__":
    inspect()
