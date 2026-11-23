# Data Analysis Notes: Ledger Reconciliation

This document records the exploratory audit of the three dataset files: `locations.csv`, `system_a.csv`, and `system_b.csv`.

---

## 1. File Summaries

### `locations.csv`
- **Total Rows**: 5 rows.
- **Columns**: `location_id`, `org_id`, `location_name`.
- **Tenant Mapping**:
  - `LOC-101`, `LOC-102`, `LOC-103` belong to `ORG-A`.
  - `LOC-201`, `LOC-202` belong to `ORG-B`.
- **Note**: This file is the single source of truth for tenant ownership. We never infer tenant by ID prefix.

### `system_a.csv`
- **Total Rows**: 120 rows.
- **Columns**: `record_id`, `location_id`, `event_date`, `category_code`, `actor_id`, `base_value`, `adjustment`, `total_value`, `state`.
- **Field observations**:
  - `record_id`: Consistent `REC-xxxx` format across all 120 rows.
  - `actor_id`: One row has an empty `actor_id` (`REC-1050`). This must be preserved as `null` in the database, not dropped.
  - `state`: 119 rows are `CONFIRMED`, 1 row is `VOIDED` (`REC-1019`).
  - Values: `base_value` + `adjustment` = `total_value`. System B values correspond to `total_value`.

### `system_b.csv`
- **Total Rows**: 121 rows (one more than System A).
- **Columns**: `entry_id`, `record_ref`, `location_id`, `recorded_on`, `value`, `label`.
- **Field observations**:
  - `entry_id`: Format `ENT/2026/4xxx`.
  - Reference inconsistencies (`record_ref`):
    - `ENT/2026/4034`: `rec1034` (lowercase without hyphen).
    - `ENT/2026/4070`: ` REC - 1070 ` (spaces around hyphen).
    - `ENT/2026/4112`: `1112` (digits only, missing prefix).
    - *Action*: Normalization regex `re.search(r"\d+", raw)` -> `f"REC-{digits}"` resolves all three cleanly.
  - Value anomalies:
    - `ENT/2026/4050`: Empty/blank value `""`. Stored as `null` (not zero).
    - `ENT/2026/4064`: Indian-style comma grouping `1,25,400.00`. Parsed as `Decimal('125400.00')`.

---

## 2. Identified Discrepancies & Ledger Irregularities

### A. Missing in B (Rows in A with zero B entries)
1. `REC-1015` (Location: `LOC-103`, Org: `ORG-A`)
2. `REC-1061` (Location: `LOC-202`, Org: `ORG-B`)

### B. Orphan in B (Row in B pointing to non-existent A record)
1. `ENT/2026/4901` (Reference: `REC-1999`, Location: `LOC-102`, Org: `ORG-A`). Does not exist in System A.

### C. Multi-Entry Records (Duplicates vs Splits)
1. **True Duplicate**: `REC-1042`
   - B has two entries (`ENT/2026/4042`, `ENT/2026/4043`), both value `112837.06`.
   - Total in A is `112837.06`, but sum of B entries is `225674.12`.
   - Flag: `DUPLICATE_IN_B`.
2. **Valid Split Entry**: `REC-1055`
   - B has two entries: `71950.93` (label: "Entry for CAT-08") and `107926.39` (label: "Entry part 2 of 2").
   - Total in A is `179877.32`.
   - Sum of B entries is `71950.93 + 107926.39 = 179877.32`.
   - Since sum matches A's total, this is a legitimate multi-part split and **must not be flagged as an error**.

### D. Value Mismatches
1. `REC-1003`: B has `94834.38` (matching A's `base_value`, but missing adjustment `26553.63` -> A's total is `121388.01`).
2. `REC-1027`: B has `61921.12` (matching A's `base_value`, missing adjustment `17337.91` -> A's total is `79259.03`).
3. `REC-1050`: B value is blank (treated as unknown / null).
4. `REC-1064`: B has `1,25,400.00` (125400.00), while A has total `183244.16`.
5. `REC-1088`: B has `108553.36` (matching A's `base_value`, missing adjustment `30394.94` -> A's total is `138948.30`).

### E. Cross-Tenant Location Trap (Data Privacy Boundary)
- `REC-1077`: System A assigns location `LOC-102` (`ORG-A`), but System B assigns location `LOC-201` (`ORG-B`).
- *Tenant Isolation Rule*: If viewing under `ORG-A`, the app must never expose the raw location ID `LOC-201` belonging to `ORG-B`, and vice versa.

### F. Date Difference
- `REC-1009`: System A date is `2026-03-31`, while System B date is `2026-04-02`.

### G. Voided Record
- `REC-1019`: Marked `VOIDED` in System A, but System B still contains active entry `ENT/2026/4019`.

---

## 3. Importer Verification Strategy
A verification script (`scripts/inspect_data.py`) tracks:
- CSV row counts: Locations (5), System A (120), System B (121).
- Unparsed values: exactly 1 blank (`REC-1050`).
- Normalized references: exactly 3 (`REC-1034`, `REC-1070`, `REC-1112`).
Running this verification ensures that database import is lossless and idempotent.
