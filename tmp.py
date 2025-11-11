import sqlite3
import csv

db_file = "db/lianjia.db"
csv_file = 'output.csv'

conn = sqlite3.connect(db_file)

cursor = conn.cursor()

cursor.execute("SELECT NAME FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

for table in tables:
    table_name = table[0]
    print(f"Processing table: {table_name}")

    rows = cursor.fetchall()

    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [column[1] for column in cursor.fetchall()]

    with open(csv_file, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        
        writer.writerow([f"Table: {table_name}"])
        
        writer.writerow(columns)
        
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        writer.writerows(rows)
        
        writer.writerow([])

conn.close()
