from django.core.management.base import BaseCommand

from women_app.myscheme_api import _expand_state_districts, _normalize_state_coverage
from women_app.models import Scheme


def _split_values(value: str):
    if not value:
        return []
    output = []
    for item in str(value).replace("\n", ",").split(","):
        cleaned = item.strip()
        if cleaned:
            output.append(cleaned)
    return output


class Command(BaseCommand):
    help = "Backfill district_coverage using known state-to-district mapping for state-targeted schemes."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None, help="Optional max records to process.")
        parser.add_argument("--dry-run", action="store_true", help="Show updates without saving.")
        parser.add_argument(
            "--only-empty",
            action="store_true",
            help="Only process records where district_coverage is empty.",
        )

    def handle(self, *args, **options):
        queryset = Scheme.objects.all().order_by("id")
        if options.get("only_empty"):
            queryset = queryset.filter(district_coverage="")
        if options.get("limit"):
            queryset = queryset[: options["limit"]]

        processed = 0
        changed = 0
        skipped = 0
        dry_run = bool(options.get("dry_run"))

        for scheme in queryset:
            processed += 1
            state_values = _normalize_state_coverage(_split_values(scheme.state_coverage))
            district_values = _expand_state_districts(state_values)
            if not district_values:
                skipped += 1
                continue

            new_value = ", ".join(district_values)
            if scheme.district_coverage == new_value:
                skipped += 1
                continue

            changed += 1
            if not dry_run:
                scheme.district_coverage = new_value
                scheme.save(update_fields=["district_coverage"])

            if processed % 200 == 0:
                self.stdout.write(
                    f"Processed {processed} | changed {changed} | skipped {skipped}"
                )

        mode = "dry-run" if dry_run else "saved"
        self.stdout.write(
            self.style.SUCCESS(
                f"District backfill complete ({mode}). Processed {processed}, changed {changed}, skipped {skipped}."
            )
        )
