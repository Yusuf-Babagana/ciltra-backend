import os
import shutil
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Restores the database from a specific backup file'

    def add_arguments(self, parser):
        parser.add_argument('filename', type=str, help='The backup filename')

    def handle(self, *args, **options):
        filename = options['filename']
        # Look in the local 'backups' folder
        backup_file = os.path.join(settings.BASE_DIR, 'backups', filename)
        db_path = os.path.join(settings.BASE_DIR, 'db.sqlite3')

        if not os.path.exists(backup_file):
            self.stdout.write(self.style.ERROR(f"Backup {filename} not found!"))
            return

        try:
            # Step 1: Create a temporary safety copy of current DB
            shutil.copy2(db_path, db_path + ".tmp")
            
            # Step 2: Overwrite current DB with backup
            shutil.copy2(backup_file, db_path)
            
            self.stdout.write(self.style.SUCCESS(f"Successfully restored {filename}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Restore failed: {e}"))