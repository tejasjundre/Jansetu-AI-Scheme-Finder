from django.core.management.base import BaseCommand

from women_app.models import Scheme
from women_app.state_portal_sync import iter_state_portal_records


class Command(BaseCommand):
    help = "Sync official state/UT government portal entries for state-specific scheme discovery."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None, help="Optional number of state portal records to sync.")
        parser.add_argument(
            "--skip-url-check",
            action="store_true",
            help="Skip portal reachability check and use the first configured URL for each state.",
        )
        parser.add_argument(
            "--timeout-seconds",
            type=int,
            default=8,
            help="HTTP timeout for URL reachability checks.",
        )

    def handle(self, *args, **options):
        processed = 0
        created = 0
        updated = 0

        for record in iter_state_portal_records(
            check_reachability=not options["skip_url_check"],
            timeout_seconds=max(2, int(options["timeout_seconds"] or 8)),
            limit=options["limit"],
        ):
            _, was_created = Scheme.objects.update_or_create(
                name=record["name"],
                defaults={
                    "category": record["category"],
                    "description": record["description"],
                    "eligibility": record["eligibility"],
                    "min_age": record["min_age"],
                    "max_age": record["max_age"],
                    "income_limit": record["income_limit"],
                    "gender": record["gender"],
                    "official_source_name": record["official_source_name"],
                    "url": record["url"],
                    "verification_status": record["verification_status"],
                    "last_verified_on": record["last_verified_on"] or None,
                    "verification_notes": record["verification_notes"],
                    "state_coverage": ", ".join(record["state_coverage"]),
                    "district_coverage": ", ".join(record["district_coverage"]),
                    "beneficiary_tags": ", ".join(record["beneficiary_tags"]),
                    "expiry_date": record["expiry_date"] or None,
                    "required_documents": "\n".join(record["required_documents"]),
                    "where_to_apply": record["where_to_apply"],
                    "offline_location": record["offline_location"],
                    "helpline": record["helpline"],
                    "effort_level": record["effort_level"],
                },
            )
            processed += 1
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"State portal sync complete. Processed {processed}, created {created}, updated {updated}."
            )
        )
