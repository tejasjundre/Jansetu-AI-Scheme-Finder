from django.core.management.base import BaseCommand

from women_app.eligibility import load_seed_schemes
from women_app.models import Scheme


class Command(BaseCommand):
    help = "Seed the scheme table using the bundled JSON dataset."

    def handle(self, *args, **options):
        processed = 0
        created_count = 0
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

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {processed} schemes and created {created_count} new records."
            )
        )
