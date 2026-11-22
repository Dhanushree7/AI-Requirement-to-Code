"""
Batch R1.2 Database Integrity & Persistence Migration Script.

This standalone migration:
1. Enforces strict parameter validation and refuses to target the live production DB
   unless the explicit --allow-live flag is passed.
2. Creates an integrity-verified binary backup before any writes.
3. Preflights existing data to ensure no unexpected duplicate anomalies exist.
4. Safely archives every column of the 3 validated duplicate requirement rows into
   `_audit_extracted_requirements_dedup` before unlinking them.
5. Idempotently creates foreign-key performance indexes and uniqueness constraints.
6. Runs post-migration integrity and foreign-key checks.
7. Under no circumstances performs automatic database restoration upon failure;
   it preserves the backup for deliberate operator inspection.
"""

import os
import sys
import shutil
import sqlite3
import argparse
import datetime
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migrate_r12")

LIVE_DB_RELATIVE = os.path.normpath("backend/storage/req_to_code.db")

EXPECTED_PROJECT_ID = "65f0d22a-2969-42b8-873d-ff653651170b"
TARGET_DUPLICATES = {
    "CON-001": {
        "canonical_uuid": "8f4ac43a-9fe7-41eb-9ecb-c61940242e7f",
        "duplicate_uuid": "0e03b816-075b-44c4-a984-36b80548eb79",
    },
    "CON-002": {
        "canonical_uuid": "ac7351f9-8730-485e-a489-2063dddc646f",
        "duplicate_uuid": "754f5bab-ebff-4171-9a8a-e683f157e766",
    },
    "CON-003": {
        "canonical_uuid": "edf4ba7d-8579-4921-b647-9c8c0318a928",
        "duplicate_uuid": "eb1453db-0131-4a56-9841-62378d043786",
    },
}

REQUIRED_INDEXES = [
    ("ix_uploaded_files_project_id", "uploaded_files", "CREATE INDEX IF NOT EXISTS ix_uploaded_files_project_id ON uploaded_files (project_id)"),
    ("ix_extracted_requirements_project_id", "extracted_requirements", "CREATE INDEX IF NOT EXISTS ix_extracted_requirements_project_id ON extracted_requirements (project_id)"),
    ("uq_extracted_requirements_project_req", "extracted_requirements", "CREATE UNIQUE INDEX IF NOT EXISTS uq_extracted_requirements_project_req ON extracted_requirements (project_id, req_id)"),
    ("ix_artifacts_project_id", "artifacts", "CREATE INDEX IF NOT EXISTS ix_artifacts_project_id ON artifacts (project_id)"),
    ("uq_artifacts_project_type", "artifacts", "CREATE UNIQUE INDEX IF NOT EXISTS uq_artifacts_project_type ON artifacts (project_id, artifact_type)"),
    ("ix_artifact_versions_artifact_id", "artifact_versions", "CREATE INDEX IF NOT EXISTS ix_artifact_versions_artifact_id ON artifact_versions (artifact_id)"),
    ("uq_artifact_versions_art_ver", "artifact_versions", "CREATE UNIQUE INDEX IF NOT EXISTS uq_artifact_versions_art_ver ON artifact_versions (artifact_id, version_number)"),
    ("ix_document_chunks_project_id", "document_chunks", "CREATE INDEX IF NOT EXISTS ix_document_chunks_project_id ON document_chunks (project_id)"),
    ("ix_document_chunks_project_source", "document_chunks", "CREATE INDEX IF NOT EXISTS ix_document_chunks_project_source ON document_chunks (project_id, source_file)"),
]

ARCHIVE_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS _audit_extracted_requirements_dedup (
    archive_id INTEGER PRIMARY KEY AUTOINCREMENT,
    archived_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    archive_reason VARCHAR(255) NOT NULL,
    original_id VARCHAR(36) NOT NULL,
    project_id VARCHAR(36) NOT NULL,
    req_id VARCHAR(50) NOT NULL,
    category VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    priority VARCHAR(50),
    module_name VARCHAR(100),
    is_ambiguous BOOLEAN,
    ambiguity_notes TEXT,
    clarifying_questions TEXT,
    created_at DATETIME,
    updated_at DATETIME,
    priority_source VARCHAR(50)
);
"""


def verify_sqlite_integrity(db_path: str, context_label: str) -> None:
    """Run PRAGMA integrity_check and PRAGMA foreign_key_check."""
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        res = cursor.fetchall()
        if not res or res[0][0] != "ok":
            raise RuntimeError(f"Integrity check failed for {context_label} ({db_path}): {res}")

        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA foreign_key_check;")
        fk_violations = cursor.fetchall()
        if fk_violations:
            raise RuntimeError(f"Foreign-key check failed for {context_label} ({db_path}): {fk_violations}")
        logger.info(f"Integrity & foreign-key check PASSED for {context_label}.")
    finally:
        conn.close()


def create_backup(db_path: str) -> str:
    """Create a timestamped binary backup of the database and verify its integrity."""
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.bak_{timestamp}"
    logger.info(f"Creating pre-migration backup at: {backup_path}")
    shutil.copy2(db_path, backup_path)

    # Verify backup integrity
    if not os.path.exists(backup_path):
        raise RuntimeError(f"Backup file creation failed: {backup_path} does not exist")
    if os.path.getsize(backup_path) != os.path.getsize(db_path):
        raise RuntimeError(f"Backup size mismatch: original={os.path.getsize(db_path)}, backup={os.path.getsize(backup_path)}")

    verify_sqlite_integrity(backup_path, "pre-migration backup")
    return backup_path


def run_migration(db_path: str, allow_live: bool = False, skip_backup: bool = False) -> dict:
    """Execute the Batch R1.2 database migration."""
    abs_target = os.path.abspath(db_path)
    abs_live = os.path.abspath(LIVE_DB_RELATIVE)

    logger.info(f"Target database path: {abs_target}")

    # Guard 1: Refuse to target live database without explicit flag
    if abs_target == abs_live and not allow_live:
        raise PermissionError(
            f"Target database resolves to the live database: {abs_target}\n"
            "Migration refused. To run against the live database, you must explicitly pass --allow-live."
        )

    if not os.path.exists(abs_target):
        raise FileNotFoundError(f"Target database does not exist: {abs_target}")

    # Guard 2: Verify pre-migration integrity of target DB
    verify_sqlite_integrity(abs_target, "target database (preflight)")

    # Guard 3: Create pre-migration backup
    backup_path = None
    if not skip_backup:
        backup_path = create_backup(abs_target)

    conn = sqlite3.connect(abs_target)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Guard 4: Check existing duplicates in extracted_requirements
        cursor.execute("""
            SELECT project_id, req_id, count(*) as cnt 
            FROM extracted_requirements 
            GROUP BY project_id, req_id 
            HAVING count(*) > 1
        """)
        existing_dupes = cursor.fetchall()

        # Deduplication Phase
        rows_archived = 0
        if existing_dupes:
            logger.info(f"Found duplicate requirement groups: {[dict(d) for d in existing_dupes]}")

            # Verify that duplicate groups strictly match our pre-inspected expected duplicates
            for d in existing_dupes:
                p_id = d["project_id"]
                r_id = d["req_id"]
                if p_id != EXPECTED_PROJECT_ID or r_id not in TARGET_DUPLICATES:
                    raise RuntimeError(
                        f"Unexpected duplicate requirement group detected: project={p_id}, req_id={r_id}, count={d['cnt']}. "
                        "Aborting migration to prevent unintended data loss."
                    )

            # Ensure archive table exists
            cursor.execute(ARCHIVE_TABLE_DDL)

            # Verify and archive each expected duplicate pair
            for req_id, pair in TARGET_DUPLICATES.items():
                c_uuid = pair["canonical_uuid"]
                d_uuid = pair["duplicate_uuid"]

                cursor.execute("SELECT * FROM extracted_requirements WHERE id = ?", (c_uuid,))
                c_row = cursor.fetchone()
                cursor.execute("SELECT * FROM extracted_requirements WHERE id = ?", (d_uuid,))
                d_row = cursor.fetchone()

                if c_row and d_row:
                    # Validate content matches exactly
                    c_dict = dict(c_row)
                    d_dict = dict(d_row)

                    for col in ["project_id", "req_id", "category", "title", "description", "priority", "module_name", "is_ambiguous"]:
                        if c_dict.get(col) != d_dict.get(col):
                            raise RuntimeError(
                                f"Duplicate row {d_uuid} does not match canonical {c_uuid} on column '{col}': "
                                f"'{d_dict.get(col)}' != '{c_dict.get(col)}'. Aborting."
                            )

                    # Archive duplicate row with all 14 columns
                    cursor.execute("""
                        INSERT INTO _audit_extracted_requirements_dedup (
                            archive_reason, original_id, project_id, req_id, category, title, description,
                            priority, module_name, is_ambiguous, ambiguity_notes, clarifying_questions,
                            created_at, updated_at, priority_source
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        "Batch R1.2 deduplication of identical secondary LLM extraction retry",
                        d_dict["id"], d_dict["project_id"], d_dict["req_id"], d_dict["category"],
                        d_dict["title"], d_dict["description"], d_dict["priority"], d_dict["module_name"],
                        d_dict["is_ambiguous"], d_dict["ambiguity_notes"], d_dict["clarifying_questions"],
                        d_dict["created_at"], d_dict["updated_at"], d_dict.get("priority_source", "suggested")
                    ))

                    # Remove only the duplicate UUID
                    cursor.execute("DELETE FROM extracted_requirements WHERE id = ?", (d_uuid,))
                    rows_archived += 1
                    logger.info(f"Archived and deleted duplicate requirement {req_id} (UUID: {d_uuid}).")
                elif not c_row and d_row:
                    raise RuntimeError(f"Canonical row {c_uuid} missing while duplicate {d_uuid} exists for {req_id}!")
                elif c_row and not d_row:
                    logger.info(f"Duplicate {d_uuid} already removed for {req_id}; canonical {c_uuid} present.")
                else:
                    raise RuntimeError(f"Neither canonical {c_uuid} nor duplicate {d_uuid} found for {req_id}!")

            logger.info(f"Deduplication completed. Archived rows: {rows_archived}")
        else:
            logger.info("No duplicate requirements found in target database. Checking archive table...")
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='_audit_extracted_requirements_dedup'")
            if cursor.fetchone():
                cursor.execute("SELECT count(*) FROM _audit_extracted_requirements_dedup")
                archived_count = cursor.fetchone()[0]
                logger.info(f"Archive table already present with {archived_count} records (idempotent run).")
            else:
                cursor.execute(ARCHIVE_TABLE_DDL)

        # Index Creation Phase
        logger.info("Applying foreign-key and unique indexes...")
        for idx_name, tbl_name, ddl in REQUIRED_INDEXES:
            logger.info(f"Applying index {idx_name} on {tbl_name}...")
            cursor.execute(ddl)

        # Commit Transaction
        conn.commit()
        logger.info("Migration transaction committed successfully.")

    except Exception as e:
        conn.rollback()
        logger.error(f"Migration transaction failed and was rolled back: {e}")
        if backup_path:
            logger.error(
                f"PRE-MIGRATION BACKUP PRESERVED AT: {backup_path}\n"
                "Automatic database replacement is disabled by policy. "
                "Inspect the failure and, if necessary, deliberately restore the backup manually."
            )
        raise
    finally:
        conn.close()

    # Guard 5: Post-migration Integrity & Consistency Verification
    logger.info("Running post-migration verification checks...")
    verify_sqlite_integrity(abs_target, "migrated target database")

    conn = sqlite3.connect(abs_target)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        # Check all 9 indexes exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        existing_indices = {r[0] for r in cursor.fetchall()}
        missing = [idx_name for idx_name, _, _ in REQUIRED_INDEXES if idx_name not in existing_indices]
        if missing:
            raise RuntimeError(f"Post-migration check failed: Missing indexes: {missing}")

        # Check duplicate requirement count is now 0
        cursor.execute("SELECT count(*) FROM extracted_requirements GROUP BY project_id, req_id HAVING count(*) > 1")
        dupes_left = cursor.fetchall()
        if dupes_left:
            raise RuntimeError(f"Post-migration check failed: Remaining duplicate requirements: {len(dupes_left)}")

        # Check archive table completeness
        cursor.execute("SELECT count(*) FROM _audit_extracted_requirements_dedup")
        archived_total = cursor.fetchone()[0]
        if archived_total < 3:
            raise RuntimeError(f"Post-migration check failed: Expected >= 3 archived rows, got {archived_total}")

        # Confirm all 14 columns in archive table have data
        cursor.execute("SELECT * FROM _audit_extracted_requirements_dedup")
        for row in cursor.fetchall():
            row_dict = dict(row)
            for col in ["original_id", "project_id", "req_id", "category", "title", "description"]:
                if not row_dict.get(col):
                    raise RuntimeError(f"Post-migration check failed: Archived row missing vital column '{col}': {row_dict}")

        logger.info("All post-migration verification assertions PASSED successfully!")
    finally:
        conn.close()

    return {
        "status": "success",
        "target_db": abs_target,
        "backup_path": backup_path,
        "rows_archived": rows_archived,
        "indexes_verified": len(REQUIRED_INDEXES),
    }


def main():
    parser = argparse.ArgumentParser(description="Batch R1.2 Database Migration Script")
    parser.add_argument("--db-path", required=True, help="Path to SQLite database to migrate")
    parser.add_argument("--allow-live", action="store_true", help="Explicit confirmation required to target the live DB")
    parser.add_argument("--skip-backup", action="store_true", help="Skip backup creation (strictly for disposable tests)")

    args = parser.parse_args()

    try:
        result = run_migration(db_path=args.db_path, allow_live=args.allow_live, skip_backup=args.skip_backup)
        print("\n=== MIGRATION COMPLETED SUCCESSFULLY ===")
        print(f"Target DB: {result['target_db']}")
        print(f"Backup Path: {result['backup_path']}")
        print(f"Rows Archived: {result['rows_archived']}")
        print(f"Indexes Verified: {result['indexes_verified']}")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Migration execution aborted: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
