import os
import pytest
from django.conf import settings
from rest_framework.test import APIClient
from reconcile.importer import DataImporter
from reconcile.models import Location, SystemARecord


@pytest.fixture(autouse=True)
def seed_data(db):
    data_dir = os.path.join(settings.BASE_DIR, "data")
    importer = DataImporter(data_dir)
    importer.import_all()


def test_org_a_never_sees_org_b_records_or_locations():
    client = APIClient()
    response = client.get("/api/disagreements/?org=ORG-A")
    assert response.status_code == 200
    data = response.data

    org_b_locations = set(Location.objects.filter(org_id="ORG-B").values_list("location_id", flat=True))
    org_b_record_ids = set(SystemARecord.objects.filter(location__org_id="ORG-B").values_list("record_id", flat=True))

    for item in data:
        # 1. Primary location must never be an ORG-B location
        assert item["location"] not in org_b_locations, f"Leaked ORG-B location {item['location']} to ORG-A"

        # 2. System A location must never be an ORG-B location
        assert item["a_location"] not in org_b_locations, f"Leaked ORG-B a_location {item['a_location']} to ORG-A"

        # 3. System B location must never expose raw ORG-B location
        assert item["b_location"] not in org_b_locations, f"Leaked ORG-B b_location {item['b_location']} to ORG-A"

        # 4. Details string must never contain raw ORG-B location IDs
        for b_loc in org_b_locations:
            assert b_loc not in (item.get("details") or ""), f"Leaked {b_loc} in details string to ORG-A"

        # 5. Record ID must never be an ORG-B owned record
        assert item["record_id"] not in org_b_record_ids, f"Leaked ORG-B record {item['record_id']} to ORG-A"


def test_org_b_never_sees_org_a_records_or_locations():
    client = APIClient()
    response = client.get("/api/disagreements/?org=ORG-B")
    assert response.status_code == 200
    data = response.data

    org_a_locations = set(Location.objects.filter(org_id="ORG-A").values_list("location_id", flat=True))
    org_a_record_ids = set(SystemARecord.objects.filter(location__org_id="ORG-A").values_list("record_id", flat=True))

    for item in data:
        # 1. Primary location must never be an ORG-A location
        assert item["location"] not in org_a_locations, f"Leaked ORG-A location {item['location']} to ORG-B"

        # 2. System A location must never be an ORG-A location
        assert item["a_location"] not in org_a_locations, f"Leaked ORG-A a_location {item['a_location']} to ORG-B"

        # 3. System B location must never expose raw ORG-A location
        assert item["b_location"] not in org_a_locations, f"Leaked ORG-A b_location {item['b_location']} to ORG-B"

        # 4. Details string must never contain raw ORG-A location IDs
        for a_loc in org_a_locations:
            assert a_loc not in (item.get("details") or ""), f"Leaked {a_loc} in details string to ORG-B"

        # 5. Record ID must never be an ORG-A owned record
        assert item["record_id"] not in org_a_record_ids, f"Leaked ORG-A record {item['record_id']} to ORG-B"


def test_trap_row_rec_1077_privacy_redaction():
    """
    REC-1077 is in System A at LOC-102 (ORG-A), but System B has it at LOC-201 (ORG-B).
    ORG-A must see the disagreement under their branch LOC-102, but System B's location
    must be redacted and never mention LOC-201.
    ORG-B must NOT see REC-1077 at all.
    """
    client = APIClient()

    # Query as ORG-A
    resp_a = client.get("/api/disagreements/?org=ORG-A")
    assert resp_a.status_code == 200
    trap_items = [it for it in resp_a.data if it["record_id"] == "REC-1077"]
    assert len(trap_items) > 0, "ORG-A should see the discrepancy for REC-1077"
    for it in trap_items:
        assert it["location"] == "LOC-102"
        assert it["b_location"] == "[REDACTED - External Branch]"
        assert "LOC-201" not in it["details"]

    # Query as ORG-B
    resp_b = client.get("/api/disagreements/?org=ORG-B")
    assert resp_b.status_code == 200
    trap_items_b = [it for it in resp_b.data if it["record_id"] == "REC-1077"]
    assert len(trap_items_b) == 0, "ORG-B must never see REC-1077"


def test_orphan_attribution_by_b_location():
    """
    Orphan entry ENT/2026/4901 has record_ref REC-1999 at location LOC-102 (ORG-A).
    It must be visible to ORG-A and completely hidden from ORG-B.
    """
    client = APIClient()

    # Visible to ORG-A
    resp_a = client.get("/api/disagreements/?org=ORG-A")
    orphans_a = [it for it in resp_a.data if it["record_id"] == "REC-1999"]
    assert len(orphans_a) == 1
    assert orphans_a[0]["reason"] == "ORPHAN_IN_B"
    assert orphans_a[0]["location"] == "LOC-102"

    # Hidden from ORG-B
    resp_b = client.get("/api/disagreements/?org=ORG-B")
    orphans_b = [it for it in resp_b.data if it["record_id"] == "REC-1999"]
    assert len(orphans_b) == 0
