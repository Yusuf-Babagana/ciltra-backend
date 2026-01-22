# scripts/backup_local.py
import shutil
import os
from datetime import datetime
from django.conf import settings

def run_backup():
    # Use Django's BASE_DIR for reliability
    db_path = os.path.join(settings.BASE_DIR, 'db.sqlite3')
    backup_dir = os.path.join(settings.BASE_DIR, 'backups')

    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_name = f"manual_backup_{timestamp}.sqlite3"
    dest_path = os.path.join(backup_dir, backup_name)
    
    shutil.copy2(db_path, dest_path)
    print(f"Backup created at {dest_path}")