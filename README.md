# DealerOS Ledger Reconciliation Web Application

A full-stack multi-tenant financial reconciliation system built with **Django REST Framework** and **React (Vite)**. The application ingests transaction ledgers from System A and System B, detects inconsistencies (missing records, duplicates, value differences, split entries, orphans, location/date mismatches), and presents discrepancies in a clean, filterable interface with strict tenant isolation.

---

## How to Run (Step-by-Step From a Clean Clone)

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm
- Git

### 1. Clone & Set Up Backend

```bash
# Clone the repository
git clone <repo-url> dealeros
cd dealeros

# Create and activate virtual environment
# Windows:
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux:
# python3 -m venv .venv
# source .venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt

# Apply migrations
cd backend
python manage.py migrate

# Losslessly import dataset (idempotent, safe to run multiple times)
python manage.py import_data

# Run backend tests
cd ..
pytest
```

### 2. Start the Backend Server

```bash
cd backend
python manage.py runserver
# Backend API will run on http://127.0.0.1:8000
```

### 3. Start the Frontend Application

Open a second terminal window:

```bash
cd dealeros/frontend
npm install
npm run dev
# Frontend will be live on http://localhost:5173
```

Open [http://localhost:5173](http://localhost:5173) in your browser to view the application.

---

## What Was Built

1. **Lossless, Idempotent Data Importer**:
   - Custom Django management command (`python manage.py import_data`) that parses `locations.csv` (5 rows), `system_a.csv` (120 rows), and `system_b.csv` (121 rows).
   - Extracts and normalizes messy references (`rec1034`, ` REC - 1070 `, `1112` $\to$ `REC-xxxx`).
   - Parses currency amounts (including Indian comma formatting `1,25,400.00` $\to$ `125400.00`), saving blank values as `null` rather than `0`.
   - Preserves raw input values (`value_raw`, `record_ref_raw`) for full auditability.

2. **Pure Python Reconciliation Engine (`reconcile/compare.py`)**:
   - Detects `MISSING_IN_B`, `ORPHAN_IN_B`, `DUPLICATE_IN_B`, `VALUE_MISMATCH`, `LOCATION_MISMATCH`, and `DATE_MISMATCH`.
   - Distinguishes valid split payments (e.g. `REC-1055` parts summing to total) from duplicate errors (e.g. `REC-1042`).

3. **Multi-Tenant REST API (`GET /api/disagreements/`)**:
   - Strictly enforces tenant isolation at the query level using `locations.csv` mappings.
   - Defends against the cross-tenant trap row (`REC-1077`): redacts external branch information so `ORG-A` never learns `ORG-B` branch identifiers, and ensures `ORG-B` cannot view `ORG-A` records.
   - Provides filtering by reason (`?reason=...`) and sorting by value (`?sort=-value`).

4. **React Frontend (Vite)**:
   - Tenant selector dropdown (`ORG-A`, `ORG-B`) dynamically querying tenant endpoints.
   - Reason filter dropdown and clickable sorting column for values and differences.
   - Displays clean empty cells (`-`) for missing values (never `0` or `null`).
   - Graceful empty states and error messaging.

5. **Automated Test Suite (23 Pytest Tests)**:
   - Covers all discrepancy categories, valid split payments, messy references, idempotent imports, API contract, and multi-tenant data isolation.

---

## What Was Deliberately Not Built

To stay focused on core correctness, data integrity, and tenant safety within the one-day scope, the following were intentionally omitted:
- **Authentication & User Management**: The API accepts `?org=ORG-A` as an explicit tenant context parameter rather than JWT/session authentication.
- **Server-Side Pagination**: With ~120 records per tenant, client-rendered tables provide immediate, low-latency filtering and sorting without pagination overhead.
- **Heavy CSS Frameworks**: Avoided Tailwind/Bootstrap overhead in favor of lightweight, custom CSS for a clean and responsive table.
- **Docker / Production Containerization**: Standard Python `venv` and npm scripts were chosen to keep clone-to-run setup under two minutes on any developer machine.

---

## How I Worked With the AI Agent

- **Tool Used**: Google Antigravity (Gemini 3.8 Flash High).
- **Task Delegation**:
  - Delegated exploratory CSV analysis and initial skeleton generation.
  - Requested targeted pure Python comparison functions and unit tests incrementally per discrepancy type.
- **What I Wrote & Directed Myself**:
  - Directed the tenant isolation architecture and designed the cross-tenant trap row redaction strategy.
  - Specified the normalization regex and strict `null` vs `0` handling rules.
  - Formulated the test matrices and verified test results against raw CSV line numbers.
- **Verification Routine**:
  - Maintained an independent data inspection script (`scripts/inspect_data.py`) to verify exact row counts (120 A rows, 121 B rows, 5 locations) before and after database imports.
  - Ran pytest suites after every single feature commit to prevent regressions.

---

## The Three Reflection Answers

### a. One thing the AI agent got wrong. How did you notice?
When implementing tenant filtering for the API, the agent initially grouped System B entries purely by their own `location_id` to detect orphans. As a result, the cross-tenant trap row `REC-1077` (which is recorded in System A under `ORG-A`'s `LOC-102`, but recorded in System B under `ORG-B`'s `LOC-201`) was incorrectly categorized as an `ORPHAN_IN_B` when querying under `ORG-B`.

I caught this immediately when running our automated tenant isolation test (`test_trap_row_rec_1077_privacy_redaction`), which threw an `AssertionError: ORG-B must never see REC-1077`. To fix this, I redesigned the tenant attribution logic: any System B entry that references a valid System A record inherits that System A record's organization ownership. Only true orphans (whose references do not exist anywhere in System A, such as `REC-1999`) rely on System B's own location for tenant mapping.

### b. The part you are least confident about, and why
The handling of System A's `VOIDED` record (`REC-1019`). System A marks this record as `VOIDED`, yet System B contains an active matching entry (`ENT/2026/4019`) with no indication of cancellation. 

Because System B's schema lacks a `state` or `status` column, it is ambiguous whether System B failed to void the entry, whether System B does not track voids at all, or whether an offset entry is missing. Currently, the system flags the matching value but leaves the status discrepancy noted in `details`. In a live production system, I would want explicit product confirmation on whether voided records in System A should trigger a dedicated `VOIDED_ACTIVE_IN_B` discrepancy or be excluded from active ledger comparisons.

### c. If you had a second day, what would you fix first?
I would build an **interactive resolution and audit trail workflow**. Currently, the reconciliation screen is read-only. In real-world dealership operations, accountants need to resolve or acknowledge discrepancies (e.g., mark a split payment as reviewed, request a correction for a misattributed branch, or trigger an adjustment voucher). Adding an audit log table that tracks who reviewed each discrepancy and records resolution notes would turn this from an inspection tool into a complete operational reconciliation workflow.
