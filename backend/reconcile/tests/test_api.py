import os
from decimal import Decimal
import pytest
from django.conf import settings
from rest_framework.test import APIClient
from reconcile.importer import DataImporter


@pytest.fixture(autouse=True)
def setup_db(db):
    """Seed the database with real imported dataset for API tests."""
    data_dir = os.path.join(settings.BASE_DIR, "data")
    importer = DataImporter(data_dir)
    importer.import_all()


def test_api_requires_org_param():
    client = APIClient()
    response = client.get("/api/disagreements/")
    assert response.status_code == 400
    assert "error" in response.data


def test_api_unknown_org_returns_404():
    client = APIClient()
    response = client.get("/api/disagreements/?org=UNKNOWN-ORG")
    assert response.status_code == 404


def test_api_get_org_a_disagreements():
    client = APIClient()
    response = client.get("/api/disagreements/?org=ORG-A")
    assert response.status_code == 200
    data = response.data
    assert isinstance(data, list)
    assert len(data) > 0

    reasons = [item["reason"] for item in data]
    assert "MISSING_IN_B" in reasons
    assert "ORPHAN_IN_B" in reasons
    assert "VALUE_MISMATCH" in reasons
    assert "LOCATION_MISMATCH" in reasons


def test_api_filter_by_reason():
    client = APIClient()
    response = client.get("/api/disagreements/?org=ORG-A&reason=VALUE_MISMATCH")
    assert response.status_code == 200
    data = response.data
    assert len(data) > 0
    assert all(item["reason"] == "VALUE_MISMATCH" for item in data)


def test_api_sort_by_value():
    client = APIClient()
    response_desc = client.get("/api/disagreements/?org=ORG-A&sort=-value")
    assert response_desc.status_code == 200
    data_desc = response_desc.data

    values = [Decimal(item["a_value"] or item["b_value"]) for item in data_desc if item["a_value"] or item["b_value"]]
    assert values == sorted(values, reverse=True)


def test_api_orgs_list():
    client = APIClient()
    response = client.get("/api/orgs/")
    assert response.status_code == 200
    assert set(response.data) == {"ORG-A", "ORG-B"}
