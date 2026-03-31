from django.core.management.base import BaseCommand

from women_app.eligibility import load_seed_schemes
from women_app.models import Scheme


class Command(BaseCommand):
    help = "Seed the scheme table using the bundled JSON dataset."

    def add_arguments(self, parser):
        parser.add_argument(
            "--if-empty",
            action="store_true",
            help="Seed only when the Scheme table is empty.",
        )
        parser.add_argument(
            "--min-count",
            type=int,
            default=None,
            help="Seed when existing Scheme count is below this threshold.",
        )

    def handle(self, *args, **options):
        existing_count = Scheme.objects.count()
        min_count = options.get("min_count")

        if options.get("if_empty") and existing_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"Scheme table already has {existing_count} records. Skipping seed (--if-empty)."
                )
            )
            return

        if min_count is not None and existing_count >= min_count:
            self.stdout.write(
                self.style.WARNING(
                    f"Scheme table has {existing_count} records (>= {min_count}). Skipping seed."
                )
            )
            return

        if min_count is not None and existing_count < min_count:
            self.stdout.write(
                self.style.WARNING(
                    f"Scheme table has only {existing_count} records (< {min_count}). Running seed."
                )
            )

        processed = 0
        created_count = 0
        updated_count = 0
        for record in load_seed_schemes():
            _, created = Scheme.objects.update_or_create(
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
                    "last_verified_on": record["last_verified_on"],
                    "verification_notes": record["verification_notes"],
                    "state_coverage": ", ".join(record["state_coverage"]),
                    "district_coverage": ", ".join(record["district_coverage"]),
                    "beneficiary_tags": ", ".join(record["beneficiary_tags"]),
                    "expiry_date": record["expiry_date"],
                    "required_documents": "\n".join(record["required_documents"]),
                    "where_to_apply": record["where_to_apply"],
                    "offline_location": record["offline_location"],
                    "helpline": record["helpline"],
                    "effort_level": record["effort_level"],
                },
            )
            processed += 1
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {processed} schemes. Created {created_count}, updated {updated_count}."
            )
        )
