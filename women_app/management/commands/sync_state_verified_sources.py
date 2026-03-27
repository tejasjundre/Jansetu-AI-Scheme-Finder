from django.core.management.base import BaseCommand

from women_app.models import Scheme
from women_app.state_source_registry import build_source_registry_record, load_state_verified_sources


def _upsert_scheme_by_url(url: str, defaults: dict):
    existing_queryset = Scheme.objects.filter(url=url).order_by("id")
    primary = existing_queryset.first()
    if primary:
        for field_name, value in defaults.items():
            setattr(primary, field_name, value)
        primary.save(update_fields=list(defaults.keys()))
        duplicate_count = existing_queryset.exclude(pk=primary.pk).count()
        if duplicate_count:
            existing_queryset.exclude(pk=primary.pk).delete()
        return False, duplicate_count

    Scheme.objects.create(url=url, **defaults)
    return True, 0


class Command(BaseCommand):
    help = "Sync verified state-level scheme sources (MahaDBT and similar official portals)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None, help="Optional number of sources to sync.")
        parser.add_argument("--skip-url-check", action="store_true", help="Do not verify URL reachability during sync.")
        parser.add_argument("--timeout-seconds", type=int, default=8, help="URL verification timeout per source.")

    def handle(self, *args, **options):
        processed = 0
        created = 0
        updated = 0
        deduplicated = 0

        sources = load_state_verified_sources()
        if options.get("limit"):
            sources = sources[: options["limit"]]

        for source in sources:
            record = build_source_registry_record(
                source,
                verify_url=not options["skip_url_check"],
                timeout_seconds=max(2, int(options["timeout_seconds"] or 8)),
            )

            defaults = {
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
            }
            was_created, removed_duplicates = _upsert_scheme_by_url(
                url=record["url"],
                defaults=defaults,
            )
            processed += 1
            deduplicated += removed_duplicates
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Verified state source sync complete. "
                f"Processed {processed}, created {created}, updated {updated}, deduplicated {deduplicated}."
            )
        )
