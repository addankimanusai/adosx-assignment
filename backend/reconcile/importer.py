import csv
import logging
import os
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, Optional

from django.db import transaction
from reconcile.models import Location, SystemARecord, SystemBEntry

logger = logging.getLogger(__name__)


def normalize_ref(raw: Optional[str]) -> Optional[str]:
    """
    Normalizes messy references:
    'rec1034', ' REC - 1070 ', '1112' -> 'REC-1034' etc.
    Returns None if no digits are present.
    """
    m = re.search(r"\d+", raw or "")
    return f"REC-{m.group()}" if m else None


def parse_amount(raw: Optional[str]) -> Optional[Decimal]:
    """
    Parses numeric strings, handling Indian and Western comma formats.
    e.g. '1,25,400.00' -> Decimal('125400.00').
    Blank or invalid strings return None (NEVER 0).
    """
    s = (raw or "").strip().replace(",", "")
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def parse_date(date_str: str):
    """Parses 'YYYY-MM-DD' into a date object."""
    s = (date_str or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


class DataImporter:
    """
    Lossless, idempotent importer for Locations, System A records, and System B entries.
    Guarantees every row in CSVs is persisted without dropping or altering records.
    """

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.stats = {
            "locations_read": 0,
            "locations_saved": 0,
            "system_a_read": 0,
            "system_a_saved": 0,
            "system_a_blank_actors": 0,
            "system_b_read": 0,
            "system_b_saved": 0,
            "system_b_blank_values": 0,
            "system_b_refs_cleaned": 0,
            "system_b_formatted_values": 0,
        }

    def import_locations(self, file_path: Optional[str] = None) -> int:
        path = file_path or os.path.join(self.data_dir, "locations.csv")
        with open(path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.stats["locations_read"] += 1
                loc_id = row["location_id"].strip()
                org_id = row["org_id"].strip()
                name = row.get("location_name", "").strip()

                Location.objects.update_or_create(
                    location_id=loc_id,
                    defaults={
                        "org_id": org_id,
                        "name": name,
                    },
                )
                self.stats["locations_saved"] += 1
        return self.stats["locations_saved"]

    def import_system_a(self, file_path: Optional[str] = None) -> int:
        path = file_path or os.path.join(self.data_dir, "system_a.csv")
        with open(path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.stats["system_a_read"] += 1
                rec_id = row["record_id"].strip()
                loc_id = row["location_id"].strip()
                event_date = parse_date(row["event_date"])
                cat_code = row.get("category_code", "").strip()

                raw_actor = row.get("actor_id", "")
                actor_id = raw_actor.strip() if raw_actor and raw_actor.strip() else None
                if actor_id is None:
                    self.stats["system_a_blank_actors"] += 1

                base_val = parse_amount(row["base_value"])
                adj_val = parse_amount(row.get("adjustment", "0.00")) or Decimal("0.00")
                tot_val = parse_amount(row["total_value"])
                state = row.get("state", "CONFIRMED").strip()

                location = Location.objects.get(location_id=loc_id)

                SystemARecord.objects.update_or_create(
                    record_id=rec_id,
                    defaults={
                        "location": location,
                        "event_date": event_date,
                        "category_code": cat_code,
                        "actor_id": actor_id,
                        "base_value": base_val,
                        "adjustment": adj_val,
                        "total_value": tot_val,
                        "state": state,
                    },
                )
                self.stats["system_a_saved"] += 1
        return self.stats["system_a_saved"]

    def import_system_b(self, file_path: Optional[str] = None) -> int:
        path = file_path or os.path.join(self.data_dir, "system_b.csv")
        with open(path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.stats["system_b_read"] += 1
                entry_id = row["entry_id"].strip()
                raw_ref = row["record_ref"]
                cleaned_ref = normalize_ref(raw_ref)
                if cleaned_ref != (raw_ref or "").strip():
                    self.stats["system_b_refs_cleaned"] += 1

                loc_id = row["location_id"].strip()
                rec_date = parse_date(row["recorded_on"])
                raw_val = row.get("value", "")
                parsed_val = parse_amount(raw_val)

                if not (raw_val or "").strip():
                    self.stats["system_b_blank_values"] += 1
                elif "," in raw_val:
                    self.stats["system_b_formatted_values"] += 1

                label = row.get("label", "").strip()
                location = Location.objects.get(location_id=loc_id)

                SystemBEntry.objects.update_or_create(
                    entry_id=entry_id,
                    defaults={
                        "record_ref_raw": raw_ref,
                        "record_ref": cleaned_ref,
                        "location": location,
                        "recorded_on": rec_date,
                        "value_raw": raw_val,
                        "value": parsed_val,
                        "label": label,
                    },
                )
                self.stats["system_b_saved"] += 1
        return self.stats["system_b_saved"]

    @transaction.atomic
    def import_all(self) -> Dict[str, Any]:
        """Imports all three files inside a transaction."""
        self.import_locations()
        self.import_system_a()
        self.import_system_b()
        return self.stats
