from django.core.management.base import BaseCommand

from women_app.eligibility import get_all_schemes


class Command(BaseCommand):
    help = "Show stale scheme records and link alerts for operations review."

    def handle(self, *args, **options):
        schemes = get_all_schemes()
        stale = [scheme for scheme in schemes if scheme["needs_freshness_review"]]
        broken = [scheme for scheme in schemes if scheme["has_broken_link_alert"]]

        self.stdout.write(self.style.WARNING(f"Stale verification reminders: {len(stale)}"))
        for scheme in stale[:10]:
            self.stdout.write(f"- {scheme['name']} | last verified: {scheme['last_verified_on']}")

        self.stdout.write(self.style.WARNING(f"Broken or missing link alerts: {len(broken)}"))
        for scheme in broken[:10]:
            self.stdout.write(f"- {scheme['name']} | source: {scheme['official_source_name'] or 'Not set'}")
