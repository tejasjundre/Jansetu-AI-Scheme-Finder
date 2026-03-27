from django.core.management import call_command
from django.core.management.base import BaseCommand

from women_app.ops_alerts import send_ops_alert


class Command(BaseCommand):
    help = "Run the daily refresh pipeline: sync, enrichment, district backfill, optional backup, and alerts."

    def add_arguments(self, parser):
        parser.add_argument("--sync-limit", type=int, default=300, help="Maximum catalog records to sync in this run.")
        parser.add_argument("--sync-page-size", type=int, default=100, help="Catalog page size (max 100).")
        parser.add_argument(
            "--detail-limit",
            type=int,
            default=200,
            help="Maximum detail enrich requests to run during sync.",
        )
        parser.add_argument(
            "--enrich-missing-limit",
            type=int,
            default=500,
            help="Maximum existing records to enrich if missing detail fields.",
        )
        parser.add_argument(
            "--district-backfill-limit",
            type=int,
            default=1000,
            help="Maximum records to process in district coverage backfill step.",
        )
        parser.add_argument("--lang", type=str, default="en", help="Detail language for enrichment.")
        parser.add_argument(
            "--delay-seconds",
            type=float,
            default=0.0,
            help="Optional delay between detail requests (both commands).",
        )
        parser.add_argument("--news-limit", type=int, default=7, help="Number of launch news entries to cache.")
        parser.add_argument("--skip-news", action="store_true", help="Skip launch-news refresh step.")
        parser.add_argument("--skip-health-report", action="store_true", help="Skip end-of-run health report.")
        parser.add_argument("--skip-state-portals", action="store_true", help="Skip syncing official state portal entries.")
        parser.add_argument(
            "--skip-state-verified-sources",
            action="store_true",
            help="Skip syncing curated/verified state sources (MahaDBT-style portals).",
        )
        parser.add_argument(
            "--crawl-state-sources",
            action="store_true",
            help="Crawl verified state sources and store discovered scheme links.",
        )
        parser.add_argument(
            "--crawl-states",
            type=str,
            default="",
            help="Optional comma-separated states for source crawling (used with --crawl-state-sources).",
        )
        parser.add_argument(
            "--crawl-limit-sources",
            type=int,
            default=12,
            help="Maximum source portals to crawl in one run (used with --crawl-state-sources).",
        )
        parser.add_argument(
            "--crawl-max-pages",
            type=int,
            default=8,
            help="Maximum pages per source for crawling (used with --crawl-state-sources).",
        )
        parser.add_argument(
            "--crawl-max-links-per-source",
            type=int,
            default=40,
            help="Maximum discovered links to keep per source (used with --crawl-state-sources).",
        )
        parser.add_argument(
            "--crawl-timeout-seconds",
            type=int,
            default=8,
            help="HTTP timeout per request in source crawl step.",
        )
        parser.add_argument("--with-backup", action="store_true", help="Create a database backup at the end.")
        parser.add_argument(
            "--backup-keep-days",
            type=int,
            default=14,
            help="Retention window for backup artifacts when --with-backup is used.",
        )
        parser.add_argument(
            "--backup-compress",
            action="store_true",
            help="Compress backup artifact when --with-backup is used.",
        )
        parser.add_argument(
            "--alert-on-failure",
            action="store_true",
            help="Send webhook alert when any step fails (uses ALERT_WEBHOOK_URL).",
        )

    def handle(self, *args, **options):
        self.stdout.write("Starting daily refresh pipeline...")
        completed_steps = []

        try:
            if not options["skip_state_portals"]:
                call_command("sync_state_portals")
                completed_steps.append("sync_state_portals")

            if not options["skip_state_verified_sources"]:
                call_command("sync_state_verified_sources")
                completed_steps.append("sync_state_verified_sources")

            if options["crawl_state_sources"]:
                crawl_kwargs = {
                    "max_pages": options["crawl_max_pages"],
                    "max_links_per_source": options["crawl_max_links_per_source"],
                    "timeout_seconds": options["crawl_timeout_seconds"],
                    "limit_sources": options["crawl_limit_sources"],
                }
                if str(options.get("crawl_states", "")).strip():
                    crawl_kwargs["states"] = options["crawl_states"]
                call_command("crawl_state_verified_sources", **crawl_kwargs)
                completed_steps.append("crawl_state_verified_sources")

            call_command(
                "sync_myscheme",
                limit=options["sync_limit"],
                page_size=options["sync_page_size"],
                enrich_details=True,
                detail_limit=options["detail_limit"],
                detail_lang=options["lang"],
                enrich_only_missing=True,
                detail_delay_seconds=options["delay_seconds"],
            )
            completed_steps.append("sync_myscheme")

            call_command(
                "enrich_myscheme_details",
                only_missing=True,
                limit=options["enrich_missing_limit"],
                lang=options["lang"],
                delay_seconds=options["delay_seconds"],
            )
            completed_steps.append("enrich_myscheme_details")

            call_command(
                "backfill_district_coverage",
                only_empty=True,
                limit=options["district_backfill_limit"],
            )
            completed_steps.append("backfill_district_coverage")

            if not options["skip_news"]:
                call_command("refresh_launch_news", limit=options["news_limit"])
                completed_steps.append("refresh_launch_news")

            if not options["skip_health_report"]:
                call_command("scheme_health_report")
                completed_steps.append("scheme_health_report")

            if options["with_backup"]:
                call_command(
                    "backup_database",
                    keep_days=options["backup_keep_days"],
                    compress=options["backup_compress"],
                )
                completed_steps.append("backup_database")

        except Exception as exc:
            if options["alert_on_failure"]:
                send_ops_alert(
                    title="JanSetu daily refresh failed",
                    body=f"Failed after steps: {', '.join(completed_steps) or 'none'}\nError: {exc}",
                    level="critical",
                )
            raise

        if options["alert_on_failure"]:
            send_ops_alert(
                title="JanSetu daily refresh succeeded",
                body=f"Completed steps: {', '.join(completed_steps)}",
                level="info",
            )
        self.stdout.write(self.style.SUCCESS("Daily refresh pipeline completed successfully."))
