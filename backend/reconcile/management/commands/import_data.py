import os
from django.conf import settings
from django.core.management.base import BaseCommand
from reconcile.importer import DataImporter


class Command(BaseCommand):
    help = "Import CSV datasets for Locations, System A records, and System B entries."

    def add_arguments(self, parser):
        parser.add_argument(
            "--data-dir",
            type=str,
            default=None,
            help="Directory containing locations.csv, system_a.csv, system_b.csv",
        )

    def handle(self, *args, **options):
        data_dir = options.get("data_dir")
        if not data_dir:
            # Check candidate paths relative to BASE_DIR or current directory
            candidates = [
                os.path.join(settings.BASE_DIR, "data"),
                os.path.join(settings.BASE_DIR, "backend", "data"),
                os.path.join(os.getcwd(), "backend", "data"),
                os.path.join(os.getcwd(), "data"),
            ]
            for c in candidates:
                if os.path.exists(os.path.join(c, "locations.csv")):
                    data_dir = c
                    break

        if not data_dir or not os.path.exists(data_dir):
            self.stderr.write(self.style.ERROR(f"Data directory not found. Candidates checked: {candidates}"))
            return

        self.stdout.write(self.style.NOTICE(f"Importing data from: {data_dir}"))
        importer = DataImporter(data_dir)
        stats = importer.import_all()

        summary_line = (
            f"A: {stats['system_a_read']} read, {stats['system_a_saved']} saved; "
            f"B: {stats['system_b_read']} read, {stats['system_b_saved']} saved; "
            f"values left empty: {stats['system_b_blank_values']}; "
            f"refs cleaned: {stats['system_b_refs_cleaned']}"
        )
        self.stdout.write(self.style.SUCCESS(summary_line))

        # Check for loss
        if stats["system_a_read"] != stats["system_a_saved"] or stats["system_b_read"] != stats["system_b_saved"]:
            self.stderr.write(self.style.ERROR("CRITICAL: Discrepancy between CSV rows read and database rows saved!"))
        else:
            self.stdout.write(self.style.SUCCESS("All rows safely and losslessly imported."))
