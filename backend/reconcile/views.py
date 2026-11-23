from decimal import Decimal
from typing import Dict, Any, List

from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from reconcile.models import Location, SystemARecord, SystemBEntry
from reconcile.compare import compare_ledgers


def root_view(request):
    """
    Friendly landing page at http://127.0.0.1:8000/ directing to the frontend UI
    and providing API links.
    """
    html = """<!DOCTYPE html>
<html>
<head>
    <title>DealerOS Ledger Reconciliation</title>
    <meta http-equiv="refresh" content="2; url=http://localhost:5173/">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; color: #1e293b; padding: 3rem; text-align: center; }
        .card { max-width: 600px; margin: 0 auto; background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 2rem; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
        h1 { font-size: 1.5rem; margin-bottom: 0.5rem; color: #0f172a; }
        p { color: #64748b; margin-bottom: 1.5rem; font-size: 0.95rem; }
        .btn { display: inline-block; background: #2563eb; color: white; padding: 0.75rem 1.5rem; border-radius: 6px; text-decoration: none; font-weight: 600; margin-bottom: 1rem; }
        .btn:hover { background: #1d4ed8; }
        .links { margin-top: 1.5rem; font-size: 0.875rem; text-align: left; background: #f1f5f9; padding: 1rem; border-radius: 6px; }
        .links ul { margin: 0.5rem 0 0 1.25rem; padding: 0; }
        .links li { margin-bottom: 0.25rem; }
        a { color: #2563eb; }
    </style>
</head>
<body>
    <div class="card">
        <h1>DealerOS Reconciliation System</h1>
        <p>The Django backend is running. Redirecting you to the React frontend UI...</p>
        <a class="btn" href="http://localhost:5173/">Open React Frontend (http://localhost:5173)</a>
        <div class="links">
            <strong>Backend API Endpoints:</strong>
            <ul>
                <li><a href="/api/orgs/">/api/orgs/</a> - List Organizations</li>
                <li><a href="/api/disagreements/?org=ORG-A">/api/disagreements/?org=ORG-A</a> - Disagreements for ORG-A</li>
                <li><a href="/api/disagreements/?org=ORG-B">/api/disagreements/?org=ORG-B</a> - Disagreements for ORG-B</li>
            </ul>
        </div>
    </div>
</body>
</html>"""
    return HttpResponse(html)


class OrgListView(APIView):
    """
    Returns available tenant organizations.
    """
    def get(self, request):
        orgs = list(Location.objects.values_list("org_id", flat=True).distinct().order_by("org_id"))
        return Response(orgs)


class DisagreementsView(APIView):
    """
    Endpoint: GET /api/disagreements/?org=ORG-A&reason=...&sort=...
    Enforces strict tenant isolation at the database query level.
    """

    def get(self, request):
        org = request.query_params.get("org")
        if not org:
            return Response(
                {"error": "The 'org' query parameter is required (e.g., ?org=ORG-A)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 1. Fetch locations owned by this tenant
        tenant_locations = set(Location.objects.filter(org_id=org).values_list("location_id", flat=True))
        if not tenant_locations:
            return Response(
                {"error": f"Organization '{org}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 2. Fetch System A records strictly owned by this tenant's locations
        a_records_qs = SystemARecord.objects.filter(location_id__in=tenant_locations)
        a_records = {
            r.record_id: {
                "record_id": r.record_id,
                "total_value": r.total_value,
                "location_id": r.location_id,
                "event_date": r.event_date,
                "state": r.state,
            }
            for r in a_records_qs
        }

        # 3. Fetch System B entries with strict tenant attribution:
        # A B entry belongs to the tenant that owns the corresponding System A record.
        # If the B entry is an orphan (does not exist anywhere in System A), ownership is
        # determined by the B entry's own location.
        all_a_record_owners = dict(SystemARecord.objects.values_list("record_id", "location__org_id"))
        all_locations = {loc.location_id: loc.org_id for loc in Location.objects.all()}

        b_entries_qs = SystemBEntry.objects.select_related("location").all()
        b_entries = []
        for b in b_entries_qs:
            a_owner = all_a_record_owners.get(b.record_ref)
            if a_owner:
                if a_owner == org:
                    b_entries.append({
                        "entry_id": b.entry_id,
                        "record_ref": b.record_ref,
                        "value": b.value,
                        "location_id": b.location_id,
                        "recorded_on": b.recorded_on,
                    })
            else:
                # True orphan: attributed by B's own location
                if b.location_id in tenant_locations:
                    b_entries.append({
                        "entry_id": b.entry_id,
                        "record_ref": b.record_ref,
                        "value": b.value,
                        "location_id": b.location_id,
                        "recorded_on": b.recorded_on,
                    })

        # 4. Run comparison engine
        raw_disagreements = compare_ledgers(a_records, b_entries, include_extra_checks=True)

        # 5. Sanitize and redact cross-tenant references (The Trap Row defense)
        sanitized: List[Dict[str, Any]] = []

        for d in raw_disagreements:
            loc_display = d.get("location")
            b_loc_display = d.get("b_location")
            details = d.get("details", "")

            # If System B recorded at an external org branch, redact it to prevent data leakage
            if b_loc_display and all_locations.get(b_loc_display) != org:
                b_loc_display = "[REDACTED - External Branch]"
                if d.get("reason") == "LOCATION_MISMATCH":
                    details = f"Location mismatch for {d.get('record_id')}: System A recorded at {d.get('a_location')}, but System B recorded at an external organization branch."

            a_val = d.get("a_value")
            b_val = d.get("b_value")
            diff = d.get("difference")

            sanitized.append({
                "reason": d.get("reason"),
                "record_id": d.get("record_id"),
                "location": loc_display,
                "a_location": d.get("a_location"),
                "b_location": b_loc_display,
                "a_value": str(a_val) if a_val is not None else None,
                "b_value": str(b_val) if b_val is not None else None,
                "difference": str(diff) if diff is not None else None,
                "details": details,
            })

        # 6. Filter by reason if requested
        reason_filter = request.query_params.get("reason")
        if reason_filter:
            sanitized = [item for item in sanitized if item["reason"] == reason_filter]

        # 7. Sort if requested (?sort=value or ?sort=-value etc.)
        sort_param = request.query_params.get("sort")
        if sort_param:
            reverse = sort_param.startswith("-")
            sort_key = sort_param.lstrip("-")

            def get_sort_value(item):
                if sort_key == "value":
                    val = item["a_value"] or item["b_value"]
                    return Decimal(val) if val is not None else Decimal("-Infinity") if not reverse else Decimal("Infinity")
                elif sort_key == "difference":
                    val = item["difference"]
                    return Decimal(val) if val is not None else Decimal("-Infinity") if not reverse else Decimal("Infinity")
                elif sort_key in item:
                    return item[sort_key] or ""
                return ""

            sanitized.sort(key=get_sort_value, reverse=reverse)

        return Response(sanitized)
