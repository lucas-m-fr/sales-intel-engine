import os
import time
from datetime import datetime

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import ARCHIVE_DIR  # noqa: E402

def monitor_progress(business_folder_name: str):
    folder_path = os.path.join(ARCHIVE_DIR, business_folder_name)
    if not os.path.exists(folder_path):
        print(f"❌ Folder {business_folder_name} not found yet...")
        return

    # 1. Check Master Leads
    master_file = os.path.join(folder_path, "master_leads.csv")
    leads_count = 0
    if os.path.exists(master_file):
        with open(master_file, 'r', encoding='utf-8') as f:
            leads_count = sum(1 for line in f) - 1

    # 2. Check Evidence Files
    evidence_dir = os.path.join(folder_path, "evidence")
    evid_count = 0
    if os.path.exists(evidence_dir):
        evid_count = len(os.listdir(evidence_dir))

    # 3. Check CSV Tables
    tables = ["Pricing.csv", "Uniqueness.csv", "Ambience.csv", "Reviews.csv"]
    completed_tables = []
    for t in tables:
        if os.path.exists(os.path.join(folder_path, t)):
            completed_tables.append(t)

    # 4. Print Status Report
    print(f"\n--- [REAL-TIME STATUS: {business_folder_name}] ---")
    print(f"🕒 Time: {datetime.now().strftime('%H:%M:%S')}")
    print(f"👥 Leads Found: {leads_count}")
    print(f"📄 Evidence Files: {evid_count} / {leads_count * 4}")
    print(f"📊 Tables Completed: {len(completed_tables)}/4 {completed_tables}")
    print(f"--------------------------------------------------\n")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        # We loop for a few iterations to show progress if run manually
        # or just once if called by a monitor
        monitor_progress(sys.argv[1])
