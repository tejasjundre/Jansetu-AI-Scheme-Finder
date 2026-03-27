import time
from datetime import date

from django.core.management.base import BaseCommand
from django.db.models import Q

from women_app.myscheme_api import enrich_summary_record
from women_app.models import Scheme


def _split_values(value: str):
    if not value:
        return []
    parts = []
    for item in str(value).replace("\n", ",").split(","):
        cleaned = item.strip()
        if cleaned:
            parts.append(cleaned)
    return parts


def _parse_date_value(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


class Command(BaseCommand):
    help = "Enrich existing myScheme database records with detail payload fields."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None, help="Optional max records to enrich in this run.")
        parser.add_argument("--lang", type=str, default="en", help="Detail language payload (en, hi, mr).")
        parser.add_argument(
            "--only-missing",
            action="store_true",
            help="Only enrich schemes missing required documents or where-to-apply fields.",
        )
        parser.add_argument(
            "--delay-seconds",
            type=float,
            default=0.0,
            help="Optional delay between detail requests.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many records would change without saving updates.",
        )

    def handle(self, *args, **options):
        queryset = Scheme.objects.filter(url__icontains="myscheme.gov.in/schemes/").order_by("id")
        if options.get("only_missing"):
            queryset = queryset.filter(Q(required_documents="") | Q(where_to_apply="") | Q(eligibility=""))

        if options.get("limit"):
            queryset = queryset[: options["limit"]]

        total = 0
        changed = 0
        unchanged = 0
        failures = 0
        lang = str(options.get("lang") or "en").strip() or "en"
        delay_seconds = max(0.0, float(options.get("delay_seconds") or 0.0))
        dry_run = bool(options.get("dry_run"))

        for scheme in queryset:
            total += 1
            record = {
                "name": scheme.name,
                "slug": scheme.url.rstrip("/").split("/schemes/")[-1] if "/schemes/" in (scheme.url or "") else "",
                "category": scheme.category,
                "description": scheme.description,
                "eligibility": scheme.eligibility,
                "min_age": scheme.min_age,
                "max_age": scheme.max_age,
                "income_limit": scheme.income_limit,
                "gender": scheme.gender,
                "official_source_name": scheme.official_source_name,
                "url": scheme.url,
                "verification_status": scheme.verification_status,
                "last_verified_on": scheme.last_verified_on.isoformat() if scheme.last_verified_on else "",
                "verification_notes": scheme.verification_notes,
                "state_coverage": _split_values(scheme.state_coverage),
                "district_coverage": _split_values(scheme.district_coverage),
                "beneficiary_tags": _split_values(scheme.beneficiary_tags),
                "expiry_date": scheme.expiry_date.isoformat() if scheme.expiry_date else "",
                "required_documents": _split_values(scheme.required_documents),
                "where_to_apply": scheme.where_to_apply,
                "offline_location": scheme.offline_location,
                "helpline": scheme.helpline,
                "effort_level": scheme.effort_level,
            }

            try:
                enriched = enrich_summary_record(record, lang=lang)
            except Exception:
                failures += 1
                continue

            updates = {
                "name": enriched.get("name", scheme.name),
                "category": enriched.get("category", scheme.category),
                "description": enriched.get("description", scheme.description),
                "eligibility": enriched.get("eligibility", scheme.eligibility),
                "min_age": enriched.get("min_age", scheme.min_age),
                "max_age": enriched.get("max_age", scheme.max_age),
                "income_limit": enriched.get("income_limit", scheme.income_limit),
                "gender": enriched.get("gender", scheme.gender),
                "official_source_name": enriched.get("official_source_name", scheme.official_source_name),
                "url": enriched.get("url", scheme.url),
                "verification_status": enriched.get("verification_status", scheme.verification_status),
                "last_verified_on": _parse_date_value(enriched.get("last_verified_on", scheme.last_verified_on)),
                "verification_notes": enriched.get("verification_notes", scheme.verification_notes),
                "state_coverage": ", ".join(enriched.get("state_coverage") or []),
                "district_coverage": ", ".join(enriched.get("district_coverage") or []),
                "beneficiary_tags": ", ".join(enriched.get("beneficiary_tags") or []),
                "expiry_date": _parse_date_value(enriched.get("expiry_date")),
                "required_documents": "\n".join(enriched.get("required_documents") or []),
                "where_to_apply": enriched.get("where_to_apply", scheme.where_to_apply),
                "offline_location": enriched.get("offline_location", scheme.offline_location),
                "helpline": enriched.get("helpline", scheme.helpline),
                "effort_level": enriched.get("effort_level", scheme.effort_level),
            }

            changed_fields = []
            for field_name, new_value in updates.items():
                current_value = getattr(scheme, field_name)
                if current_value != new_value:
                    setattr(scheme, field_name, new_value)
                    changed_fields.append(field_name)

            if changed_fields:
                changed += 1
                if not dry_run:
                    scheme.save(update_fields=changed_fields)
            else:
                unchanged += 1

            if delay_seconds > 0:
                time.sleep(delay_seconds)

            if total % 100 == 0:
                self.stdout.write(
                    f"Processed {total} records | changed {changed} | unchanged {unchanged} | failures {failures}"
                )

        mode = "dry-run" if dry_run else "saved"
        self.stdout.write(
            self.style.SUCCESS(
                f"Detail enrichment complete ({mode}). Processed {total}, changed {changed}, unchanged {unchanged}, failures {failures}."
            )
        )
