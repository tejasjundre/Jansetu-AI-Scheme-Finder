import time

from django.core.management.base import BaseCommand

from women_app.myscheme_api import enrich_summary_record, iter_catalog_records
from women_app.models import Scheme


class Command(BaseCommand):
    help = "Import the official myScheme catalogue into the local Scheme table."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None, help="Optional maximum number of schemes to import.")
        parser.add_argument(
            "--page-size",
            type=int,
            default=100,
            help="Number of records to fetch per API request. The official API currently allows up to 100.",
        )
        parser.add_argument(
            "--enrich-details",
            action="store_true",
            help="Fetch each scheme detail payload and enrich documents/application fields.",
        )
        parser.add_argument(
            "--detail-lang",
            type=str,
            default="en",
            help="Language for detail enrichment payload (en, hi, mr). Default is en.",
        )
        parser.add_argument(
            "--detail-limit",
            type=int,
            default=None,
            help="Optional maximum number of detail enrichment requests in this run.",
        )
        parser.add_argument(
            "--enrich-only-missing",
            action="store_true",
            help="When used with --enrich-details, only call detail API for schemes missing docs or apply steps.",
        )
        parser.add_argument(
            "--detail-delay-seconds",
            type=float,
            default=0.0,
            help="Optional delay between detail API requests (for gentle rate control).",
        )

    def handle(self, *args, **options):
        processed = 0
        created = 0
        updated = 0
        enriched = 0
        detail_failed = 0

        enrich_details = bool(options.get("enrich_details"))
        enrich_only_missing = bool(options.get("enrich_only_missing"))
        detail_limit = options.get("detail_limit")
        detail_lang = str(options.get("detail_lang") or "en").strip() or "en"
        detail_delay = max(0.0, float(options.get("detail_delay_seconds") or 0.0))
        detail_calls = 0

        for record in iter_catalog_records(size=options["page_size"], limit=options["limit"]):
            should_enrich = enrich_details
            if should_enrich and detail_limit is not None and detail_calls >= detail_limit:
                should_enrich = False

            if should_enrich and enrich_only_missing:
                existing = (
                    Scheme.objects.filter(url=record["url"])
                    .values("required_documents", "where_to_apply")
                    .first()
                )
                if existing and existing.get("required_documents") and existing.get("where_to_apply"):
                    should_enrich = False

            if should_enrich:
                try:
                    enriched_record = enrich_summary_record(record, lang=detail_lang)
                    if enriched_record != record:
                        enriched += 1
                    record = enriched_record
                except Exception:
                    detail_failed += 1
                detail_calls += 1
                if detail_delay > 0:
                    time.sleep(detail_delay)

            _, was_created = Scheme.objects.update_or_create(
                url=record["url"],
                defaults={
                    "name": record["name"],
                    "category": record["category"],
                    "description": record["description"],
                    "eligibility": record["eligibility"],
                    "min_age": record["min_age"],
                    "max_age": record["max_age"],
                    "income_limit": record["income_limit"],
                    "gender": record["gender"],
                    "official_source_name": record["official_source_name"],
                    "verification_status": record["verification_status"],
                    "last_verified_on": record["last_verified_on"],
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

            if processed % 250 == 0:
                self.stdout.write(f"Imported {processed} schemes...")

        self.stdout.write(
            self.style.SUCCESS(
                (
                    "myScheme sync complete. "
                    f"Processed {processed}, created {created}, updated {updated}, "
                    f"details_enriched {enriched}, detail_failures {detail_failed}."
                )
            )
        )
