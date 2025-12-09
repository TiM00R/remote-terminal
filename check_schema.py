import sqlite3

conn = sqlite3.connect('data/remote_terminal.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
tables = cursor.fetchall()

print('=== ALL TABLES ===')
for table in tables:
    print(f'  - {table[0]}')

print('\n=== RECIPE-RELATED TABLES ===')
for table in tables:
    if 'recipe' in table[0].lower():
        table_name = table[0]
        print(f'\nTable: {table_name}')
        cursor.execute(f'PRAGMA table_info({table_name});')
        columns = cursor.fetchall()
        for col in columns:
            null_str = 'NOT NULL' if col[3] else ''
            pk_str = 'PK' if col[5] else ''
            print(f'  {col[1]:25} {col[2]:15} {null_str:10} {pk_str}')

conn.close()
