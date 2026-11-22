import sqlite3
import os
import sys

def run_migration():
    db_path = os.path.join(os.path.dirname(__file__), "..", "storage", "req_to_code.db")
    db_path = os.path.abspath(db_path)
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Update users table
    cursor.execute("PRAGMA table_info(users)")
    user_cols = [col[1] for col in cursor.fetchall()]
    if "is_superuser" not in user_cols:
        print("Adding is_superuser to users...")
        cursor.execute("ALTER TABLE users ADD COLUMN is_superuser BOOLEAN DEFAULT 0 NOT NULL")
        # Existing users become superuser
        cursor.execute("UPDATE users SET is_superuser = 1")
        conn.commit()
        print("Added is_superuser and set existing users as superuser.")
    else:
        print("is_superuser already exists on users.")

    # 2. Update projects table
    cursor.execute("PRAGMA table_info(projects)")
    project_cols = [col[1] for col in cursor.fetchall()]
    if "user_id" not in project_cols:
        print("Adding user_id to projects...")
        cursor.execute("ALTER TABLE projects ADD COLUMN user_id VARCHAR(36)")
        conn.commit()
        print("Added user_id column.")
    else:
        print("user_id already exists on projects.")

    # Assign existing projects to the first user
    cursor.execute("SELECT id FROM users ORDER BY created_at ASC LIMIT 1")
    user_row = cursor.fetchone()
    if user_row:
        first_user_id = user_row[0]
        cursor.execute("UPDATE projects SET user_id = ? WHERE user_id IS NULL", (first_user_id,))
        conn.commit()
        print(f"Assigned orphan projects to user {first_user_id}")
    else:
        print("No users found to assign projects.")

    # Create index on projects(user_id) if not exists
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_projects_user_id ON projects(user_id)")
    conn.commit()

    # Verification
    cursor.execute("SELECT id, email, is_superuser FROM users")
    print("Users:", cursor.fetchall())
    cursor.execute("SELECT id, name, user_id FROM projects")
    print("Projects:", cursor.fetchall())

    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    run_migration()
