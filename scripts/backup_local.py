import os
import shutil
from datetime import datetime
import django

# This allows the script to be run standalone or via Django views
def run_backup():
    # Set up Django environment if not already loaded
    if not os.environ.get('DJANGO_SETTINGS_MODULE'):
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ciltra_platform.settings')
        django.setup()

    from django.conf import settings
    
    # Dynamic paths based on the project root
    db_path = os.path.join(settings.BASE_DIR, 'db.sqlite3')
    backup_dir = os.path.join(settings.BASE_DIR, 'backups')

    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_name = f"manual_backup_{timestamp}.sqlite3"
    dest_path = os.path.join(backup_dir, backup_name)
    
    if os.path.exists(db_path):
        shutil.copy2(db_path, dest_path)
        print(f"✅ Backup created successfully at {dest_path}")
    else:
        print(f"❌ Error: Database not found at {db_path}")

if __name__ == "__main__":
    run_backup()