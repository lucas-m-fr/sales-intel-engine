import os
import csv

def validate_table(business_folder: str, table_name: str):
    table_path = os.path.join(business_folder, f"{table_name}.csv")
    if not os.path.exists(table_path): return

    evidence_folder = os.path.join(business_folder, "evidence")
    with open(table_path, 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    validated = []
    for row in rows:
        evidence_file = os.path.join(evidence_folder, f"{row['lead_id']}_{table_name}.txt")
        if os.path.exists(evidence_file):
            validated.append(row)

    if validated:
        with open(table_path.replace('.csv', '_verified.csv'), 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(validated)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        for table in ["Pricing", "Uniqueness", "Ambience", "Reviews"]:
            validate_table(sys.argv[1], table)
