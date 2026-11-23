from decimal import Decimal
from django.db import models


class Location(models.Model):
    """
    Physical branch belonging to exactly one organization (tenant).
    This model is the single source of truth for org_id mapping.
    """
    location_id = models.CharField(max_length=50, primary_key=True)
    org_id = models.CharField(max_length=50, db_index=True)
    name = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return f"{self.location_id} ({self.org_id})"


class SystemARecord(models.Model):
    """
    Ledger record from System A.
    """
    record_id = models.CharField(max_length=50, primary_key=True)
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name="system_a_records",
        to_field="location_id"
    )
    event_date = models.DateField()
    category_code = models.CharField(max_length=50, blank=True, default="")
    actor_id = models.CharField(max_length=50, null=True, blank=True)
    base_value = models.DecimalField(max_digits=14, decimal_places=2)
    adjustment = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_value = models.DecimalField(max_digits=14, decimal_places=2)
    state = models.CharField(max_length=20, default="CONFIRMED")

    def __str__(self):
        return f"SystemA {self.record_id} - {self.total_value} ({self.location_id})"


class SystemBEntry(models.Model):
    """
    Ledger entry from System B.
    Points back to System A via `record_ref`, but does not use a database Foreign Key
    constraint to SystemARecord so orphan entries (records missing in A) can be persisted safely.
    Raw fields store the exact source CSV string to ensure no information is lost.
    """
    entry_id = models.CharField(max_length=50, primary_key=True)
    record_ref_raw = models.CharField(max_length=100)
    record_ref = models.CharField(max_length=50, db_index=True, null=True, blank=True)
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name="system_b_entries",
        to_field="location_id"
    )
    recorded_on = models.DateField()
    value_raw = models.CharField(max_length=100, blank=True, default="")
    value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    label = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return f"SystemB {self.entry_id} -> {self.record_ref} - {self.value} ({self.location_id})"
