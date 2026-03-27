from django.core.management.base import BaseCommand

from women_app.location_data import canonical_state_name
from women_app.models import Scheme
from women_app.state_source_crawler import build_crawled_scheme_record, crawl_source_for_scheme_links
from women_app.state_source_registry import load_state_verified_sources


def _safe_console_text(value):
    return str(value).encode("ascii", "backslashreplace").decode("ascii")


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
    help = (
        "Crawl verified state sources (MahaDBT-style portals and official state sources) "
        "to discover additional scheme/application links."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--states",
            type=str,
            default="",
            help="Optional comma-separated state names (for example: Maharashtra,Gujarat).",
        )
        parser.add_argument(
            "--limit-sources",
            type=int,
            default=None,
            help="Optional number of source portals to crawl in this run.",
        )
        parser.add_argument("--max-pages", type=int, default=12, help="Maximum pages to crawl per source.")
        parser.add_argument(
            "--max-links-per-source",
            type=int,
            default=80,
            help="Maximum discovered scheme links to store per source.",
        )
        parser.add_argument(
            "--timeout-seconds",
            type=int,
            default=8,
            help="HTTP timeout for crawling requests.",
        )

    def handle(self, *args, **options):
        state_filters = {
            canonical_state_name(value.strip())
            for value in str(options.get("states", "")).split(",")
            if value.strip()
        }
        state_filters.discard("")

        sources = load_state_verified_sources()
        if state_filters:
            sources = [source for source in sources if source["state"] in state_filters]
        if options.get("limit_sources"):
            sources = sources[: options["limit_sources"]]

        processed_sources = 0
        failed_sources = 0
        discovered_total = 0
        created = 0
        updated = 0
        deduplicated = 0

        for source in sources:
            processed_sources += 1
            try:
                discovered_links = crawl_source_for_scheme_links(
                    source_url=source["url"],
                    max_pages=max(1, int(options.get("max_pages") or 12)),
                    max_links=max(1, int(options.get("max_links_per_source") or 80)),
                    timeout_seconds=max(2, int(options.get("timeout_seconds") or 8)),
                )
            except Exception as exc:
                failed_sources += 1
                self.stdout.write(
                    self.style.WARNING(
                        _safe_console_text(
                            f"Failed to crawl {source['source_name']} ({source['url']}): {exc}"
                        )
                    )
                )
                continue

            source_discovered = 0
            for discovered in discovered_links:
                discovered_url = str(discovered.get("url", "")).strip().rstrip("/")
                source_url = str(source.get("url", "")).strip().rstrip("/")
                if not discovered_url or discovered_url == source_url:
                    continue

                record = build_crawled_scheme_record(source, discovered)
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
                source_discovered += 1
                deduplicated += removed_duplicates
                if was_created:
                    created += 1
                else:
                    updated += 1

            discovered_total += source_discovered
            self.stdout.write(
                f"[{source['state']}] {source['source_name']}: {source_discovered} discovered links"
            )

        self.stdout.write(
            self.style.SUCCESS(
                "State source crawl complete. "
                f"Processed sources {processed_sources}, failed {failed_sources}, "
                f"discovered links {discovered_total}, created {created}, updated {updated}, "
                f"deduplicated {deduplicated}."
            )
        )
