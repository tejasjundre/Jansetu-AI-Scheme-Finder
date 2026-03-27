import gzip
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


def _safe_timestamp():
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


class Command(BaseCommand):
    help = "Create a database backup artifact (sqlite copy or JSON fixture fallback)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            type=str,
            default=str(Path(settings.BASE_DIR) / "backups"),
            help="Directory where backups are stored.",
        )
        parser.add_argument(
            "--keep-days",
            type=int,
            default=14,
            help="Delete backup files older than this many days (0 disables cleanup).",
        )
        parser.add_argument(
            "--compress",
            action="store_true",
            help="Compress backup artifact with gzip.",
        )

    def handle(self, *args, **options):
        output_dir = Path(options["output_dir"]).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        db_settings = settings.DATABASES.get("default", {})
        engine = str(db_settings.get("ENGINE", ""))
        timestamp = _safe_timestamp()

        if engine.endswith("sqlite3"):
            db_path = Path(str(db_settings.get("NAME", ""))).resolve()
            if not db_path.exists():
                self.stdout.write(self.style.ERROR(f"SQLite database file not found: {db_path}"))
                return
            backup_name = f"db_sqlite_{timestamp}.sqlite3"
            backup_path = output_dir / backup_name
            shutil.copy2(db_path, backup_path)
        else:
            backup_name = f"db_fixture_{timestamp}.json"
            backup_path = output_dir / backup_name
            with backup_path.open("w", encoding="utf-8") as handle:
                call_command("dumpdata", "--natural-foreign", "--natural-primary", stdout=handle)

        if options["compress"]:
            compressed_path = backup_path.with_suffix(backup_path.suffix + ".gz")
            with backup_path.open("rb") as source:
                with gzip.open(compressed_path, "wb") as target:
                    shutil.copyfileobj(source, target)
            backup_path.unlink(missing_ok=True)
            backup_path = compressed_path

        keep_days = int(options.get("keep_days") or 0)
        if keep_days > 0:
            cutoff = datetime.utcnow() - timedelta(days=keep_days)
            for file_path in output_dir.iterdir():
                if not file_path.is_file():
                    continue
                modified_time = datetime.utcfromtimestamp(file_path.stat().st_mtime)
                if modified_time < cutoff:
                    file_path.unlink(missing_ok=True)

        self.stdout.write(self.style.SUCCESS(f"Backup created: {backup_path}"))
