import os
import sys
import sqlite3
import argparse
import datetime
from pathlib import Path

# Add project root directory to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

BACKUP_DIR = PROJECT_ROOT / "backups"
DB_FILE = PROJECT_ROOT / "instance" / "college.db"
if not DB_FILE.exists():
    DB_FILE = PROJECT_ROOT / "college.db"

def ensure_backup_dir():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

def create_backup():
    """
    Uses SQLite's online backup API (sqlite3.connect().backup()) to safely create an
    atomic snapshot of the database even while the web server is actively handling requests.
    """
    ensure_backup_dir()
    if not DB_FILE.exists():
        print(f"[ERROR] Database file not found at '{DB_FILE}'!")
        sys.exit(1)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"college_db_backup_{timestamp}.db"
    backup_filepath = BACKUP_DIR / backup_filename

    print(f"[INFO] Initiating online database backup from '{DB_FILE.name}'...")
    try:
        source_conn = sqlite3.connect(str(DB_FILE))
        dest_conn = sqlite3.connect(str(backup_filepath))

        # Perform atomic online backup
        with dest_conn:
            source_conn.backup(dest_conn)

        source_conn.close()
        dest_conn.close()

        size_kb = backup_filepath.stat().st_size / 1024
        print(f"[SUCCESS] Backup created successfully: {backup_filepath.name} ({size_kb:.2f} KB)")
        print(f"          Location: {backup_filepath}")
        return str(backup_filepath)

    except Exception as e:
        print(f"[ERROR] Backup failed with error: {e}")
        sys.exit(1)

def list_backups():
    """
    Lists all available database backup files with timestamp and file size.
    """
    ensure_backup_dir()
    backups = sorted(BACKUP_DIR.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not backups:
        print("[INFO] No backup files found in 'backups/' directory.")
        return []

    print("\n==================================================")
    print(" AVAILABLE DATABASE BACKUPS                       ")
    print("==================================================")
    for idx, b in enumerate(backups, 1):
        size_kb = b.stat().st_size / 1024
        mtime = datetime.datetime.fromtimestamp(b.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f" [{idx}] {b.name} ({size_kb:.2f} KB) - Created: {mtime}")
    print("==================================================\n")
    return backups

def restore_backup(backup_name_or_path):
    """
    Restores the database from a specified backup snapshot file.
    """
    ensure_backup_dir()
    target_backup = Path(backup_name_or_path)
    if not target_backup.is_absolute():
        target_backup = BACKUP_DIR / backup_name_or_path

    if not target_backup.exists():
        print(f"[ERROR] Specified backup file '{target_backup}' does not exist!")
        sys.exit(1)

    print(f"[WARNING] Restoring database from backup snapshot: {target_backup.name}...")
    try:
        source_conn = sqlite3.connect(str(target_backup))
        dest_conn = sqlite3.connect(str(DB_FILE))

        with dest_conn:
            source_conn.backup(dest_conn)

        source_conn.close()
        dest_conn.close()

        print(f"[SUCCESS] Database restored successfully to '{DB_FILE.name}'!")
    except Exception as e:
        print(f"[ERROR] Restoration failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-Tenant College Database Backup & Restore Tool")
    parser.add_argument("--backup", action="store_true", help="Create an online database backup snapshot")
    parser.add_argument("--list", action="store_true", help="List available database backup snapshots")
    parser.add_argument("--restore", type=str, help="Restore database from specified backup filename or path")

    args = parser.parse_args()

    if args.backup:
        create_backup()
    elif args.list:
        list_backups()
    elif args.restore:
        restore_backup(args.restore)
    else:
        parser.print_help()
