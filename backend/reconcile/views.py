from decimal import Decimal
from typing import Dict, Any, List

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from reconcile.models import Location, SystemARecord, SystemBEntry
from reconcile.compare import compare_ledgers


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

        # 3. Fetch System B entries relevant to this tenant:
        # Entries that are either at tenant locations (including orphans) OR match tenant A records
        tenant_a_record_ids = set(a_records.keys())
        b_entries_qs = SystemBEntry.objects.filter(
            location_id__in=tenant_locations
        ) | SystemBEntry.objects.filter(
            record_ref__in=tenant_a_record_ids
        )
        b_entries_qs = b_entries_qs.distinct()

        b_entries = [
            {
                "entry_id": b.entry_id,
                "record_ref": b.record_ref,
                "value": b.value,
                "location_id": b.location_id,
                "recorded_on": b.recorded_on,
            }
            for b in b_entries_qs
        ]

        # 4. Run comparison engine
        raw_disagreements = compare_ledgers(a_records, b_entries, include_extra_checks=True)

        # 5. Sanitize and redact cross-tenant references (The Trap Row defense)
        all_locations = {loc.location_id: loc.org_id for loc in Location.objects.all()}
        sanitized: List[Dict[str, Any]] = []

        for d in raw_disagreements:
            # Check if this item belongs to this org
            item_a_loc = d.get("a_location")
            item_b_loc = d.get("b_location")

            # Determine ownership:
            # If A record exists, A's location defines tenant ownership.
            # If orphan (no A record), B's location defines tenant ownership.
            item_org = None
            if item_a_loc:
                item_org = all_locations.get(item_a_loc)
            elif item_b_loc:
                item_org = all_locations.get(item_b_loc)

            # Strict tenant boundary: only include if owned by queried tenant
            if item_org != org:
                continue

            # Redact cross-tenant location if B recorded an external branch
            loc_display = d.get("location")
            b_loc_display = d.get("b_location")
            details = d.get("details", "")

            if b_loc_display and all_locations.get(b_loc_display) != org:
                b_loc_display = "[REDACTED - External Branch]"
                if d.get("reason") == "LOCATION_MISMATCH":
                    details = f"Location mismatch for {d.get('record_id')}: System A recorded at {item_a_loc}, but System B recorded at an external organization branch."

            # Format decimals for clean JSON serialization
            a_val = d.get("a_value")
            b_val = d.get("b_value")
            diff = d.get("difference")

            sanitized.append({
                "reason": d.get("reason"),
                "record_id": d.get("record_id"),
                "location": loc_display,
                "a_location": item_a_loc,
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
                    # Sort primarily by a_value or b_value
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
