from django.core.management.base import BaseCommand

from women_app.news_feed import get_launch_news


class Command(BaseCommand):
    help = "Refresh and warm the launch news cache from official PIB feed."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=7, help="How many news items to cache")

    def handle(self, *args, **options):
        limit = max(1, min(int(options["limit"]), 20))
        items = get_launch_news(limit=limit)
        self.stdout.write(self.style.SUCCESS(f"Cached {len(items)} launch news item(s)."))
