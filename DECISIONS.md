# Engineering Decisions

## Decision: Compare System B's value against System A's total_value
- Rejected: Comparing against `base_value`
- Why: In System A, `total_value` equals `base_value + adjustment`. Spot checking matching records (e.g., `REC-1001`, `REC-1002`) confirms that System B's `value` is recorded against the final adjusted total, not the pre-adjustment base value.

## Decision: Store empty and unparseable values as null rather than 0
- Rejected: Coercing blank or malformed values to `Decimal('0.00')`
- Why: A blank value (`ENT/2026/4050`) denotes an unknown or unrecorded amount, whereas 0 is a valid financial transaction quantity. Coercing unknown to zero corrupts reconciliation differences and masks missing data.

## Decision: Normalize messy references using digit extraction
- Rejected: Exact string matching or dropping malformed reference rows
- Why: Entries like `rec1034`, ` REC - 1070 `, and `1112` reference actual System A records `REC-1034`, `REC-1070`, and `REC-1112`. Extracting digits into canonical `REC-{digits}` format prevents false orphan/missing discrepancies.

## Decision: Treat multi-entry B rows that sum to A's total as valid splits
- Rejected: Flagging all multi-entry System B rows as `DUPLICATE_IN_B`
- Why: In `REC-1055`, System B recorded two entries (`71950.93` and `107926.39`) labeled "part 2 of 2" that sum exactly to System A's total `179877.32`. This represents an installment/split payment, whereas `REC-1042` is a duplicate payment totaling double A's total.

## Decision: Use DecimalField instead of FloatField for all currency values
- Rejected: Using Python `float` or database floating-point columns
- Why: Binary floating-point representation causes IEEE 754 precision issues (e.g., `0.1 + 0.2 != 0.3`). Exact fixed-point `Decimal` with 2 decimal places prevents false discrepancies in ledger reconciliation.

## Decision: Avoid database foreign key constraint from System B to System A
- Rejected: Enforcing Django `ForeignKey(SystemARecord)` on `SystemBEntry.record_ref`
- Why: System B contains orphan entry `ENT/2026/4901` (`REC-1999`) which does not exist in System A. A relational foreign key would reject the row or crash the import, violating the lossless ingestion requirement.

## Decision: Redact cross-tenant location on the trap row (REC-1077)
- Rejected: Displaying raw `LOC-201` to `ORG-A` or displaying `REC-1077` as an orphan to `ORG-B`
- Why: `REC-1077` belongs to `ORG-A` (`LOC-102`), but B misallocated it to `LOC-201` (`ORG-B`). Disclosing `LOC-201` to `ORG-A` leaks `ORG-B`'s internal branch ID. Attributing ownership to `ORG-A` while masking B's branch to `[REDACTED - External Branch]` maintains complete privacy.

## Decision: Include Date and Location differences as explicit configurable checks
- Rejected: Restricting reconciliation solely to existence and amount checks
- Why: In distributed multi-branch architectures, branch misallocation (cross-location recording) and settlement timing lags (`DATE_MISMATCH`, e.g. `REC-1009`) are critical ledger audit findings that operational accountants must see.

## Decision: Treat System A VOIDED record with active System B entry as discrepancy
- Rejected: Silently dropping voided records or assuming System B automatically honors voided status
- Why: In `REC-1019`, System A marked the record `VOIDED`, yet System B holds an active, unreversed entry (`ENT/2026/4019`). Since System B does not provide a void/reversal column, surfacing it alerts the auditor to an unreversed debit.
