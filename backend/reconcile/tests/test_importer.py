import os
from decimal import Decimal
import pytest
from django.conf import settings
from reconcile.importer import normalize_ref, parse_amount, DataImporter
from reconcile.models import Location, SystemARecord, SystemBEntry


def test_normalize_ref():
    assert normalize_ref("rec1034") == "REC-1034"
    assert normalize_ref(" REC - 1070 ") == "REC-1070"
    assert normalize_ref("1112") == "REC-1112"
    assert normalize_ref("REC-1001") == "REC-1001"
    assert normalize_ref("") is None
    assert normalize_ref(None) is None
    assert normalize_ref("invalid") is None


def test_parse_amount():
    assert parse_amount("1,25,400.00") == Decimal("125400.00")
    assert parse_amount("94834.38") == Decimal("94834.38")
    assert parse_amount("0.00") == Decimal("0.00")
    # Blank or whitespace MUST be None, never 0
    assert parse_amount("") is None
    assert parse_amount("   ") is None
    assert parse_amount(None) is None
    assert parse_amount("bad_text") is None


@pytest.mark.django_db
def test_importer_lossless_and_idempotent():
    data_dir = os.path.join(settings.BASE_DIR, "data")
    importer = DataImporter(data_dir)

    # First run
    stats1 = importer.import_all()
    assert stats1["locations_saved"] == 5
    assert stats1["system_a_saved"] == 120
    assert stats1["system_b_saved"] == 121
    assert stats1["system_b_blank_values"] == 1
    assert stats1["system_b_refs_cleaned"] == 3

    assert Location.objects.count() == 5
    assert SystemARecord.objects.count() == 120
    assert SystemBEntry.objects.count() == 121

    # Check preserved dirty rows
    blank_actor = SystemARecord.objects.get(record_id="REC-1050")
    assert blank_actor.actor_id is None

    blank_val_b = SystemBEntry.objects.get(entry_id="ENT/2026/4050")
    assert blank_val_b.value is None
    assert blank_val_b.value_raw == ""

    comma_val_b = SystemBEntry.objects.get(entry_id="ENT/2026/4064")
    assert comma_val_b.value == Decimal("125400.00")
    assert comma_val_b.value_raw == "1,25,400.00"

    cleaned_ref_b = SystemBEntry.objects.get(entry_id="ENT/2026/4034")
    assert cleaned_ref_b.record_ref_raw == "rec1034"
    assert cleaned_ref_b.record_ref == "REC-1034"

    # Second run to prove idempotency (no row duplication)
    importer2 = DataImporter(data_dir)
    stats2 = importer2.import_all()
    assert stats2["locations_saved"] == 5
    assert stats2["system_a_saved"] == 120
    assert stats2["system_b_saved"] == 121

    assert Location.objects.count() == 5
    assert SystemARecord.objects.count() == 120
    assert SystemBEntry.objects.count() == 121
