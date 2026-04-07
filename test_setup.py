import os
import sqlite3
from pathlib import Path

print("="*50)
print("🔍 Testing Setup")
print("="*50)

# Check current directory
current_dir = Path.cwd()
print(f"\n📁 Current directory: {current_dir}")

# Check instance directory
instance_dir = current_dir / 'instance'
print(f"\n📁 Instance directory: {instance_dir}")
print(f"   Exists: {instance_dir.exists()}")

if not instance_dir.exists():
    print("   Creating instance directory...")
    instance_dir.mkdir(exist_ok=True)
    print(f"   Created: {instance_dir.exists()}")

# Check database file
db_file = instance_dir / 'insightflow.db'
print(f"\n📁 Database file: {db_file}")
print(f"   Exists: {db_file.exists()}")

if not db_file.exists():
    print("   Creating database file...")
    db_file.touch()
    print(f"   Created: {db_file.exists()}")

# Test write permissions
try:
    test_file = instance_dir / 'test_write.txt'
    test_file.write_text('test')
    test_file.unlink()
    print("\n✅ Write permission: OK")
except Exception as e:
    print(f"\n❌ Write permission error: {e}")

# Test SQLite connection
try:
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS test (id INTEGER)')
    cursor.execute('DROP TABLE test')
    conn.close()
    print("✅ SQLite connection: OK")
except Exception as e:
    print(f"❌ SQLite connection error: {e}")

print("\n" + "="*50)
print("📊 Database Connection String")
print("="*50)
db_url = str(db_file).replace('\\', '/')
print(f"sqlite:///{db_url}")

print("\n" + "="*50)
print("✅ Setup test complete!")
print("="*50)