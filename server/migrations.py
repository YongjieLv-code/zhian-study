from pathlib import Path

from sqlalchemy import MetaData, inspect, select
from sqlalchemy.orm import Session

from .backups import COLLECTIONS, DELETE_ORDER, canonical, snapshot
from .database import Account, Base, LOCAL_ACCOUNT, Profile, ROOT, today
from .services import seed


def backup_directory(engine, settings):
    if settings.backup_dir is not None:
        return settings.backup_dir.resolve()
    if engine.dialect.name == "sqlite" and engine.url.database not in {None, "", ":memory:"}:
        return Path(engine.url.database).resolve().parent / "backups"
    return ROOT / "data" / "backups"


def initialize(engine, directory):
    """Upgrade v0.1 in one transaction, with an original-data snapshot first."""
    with engine.connect() as connection:
        if engine.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            connection.begin()
            if engine.dialect.name == "postgresql":
                connection.exec_driver_sql("SELECT pg_advisory_xact_lock(904291)")
        try:
            tables = inspect(connection)
            legacy = tables.has_table("subjects") and "account_id" not in {column["name"] for column in tables.get_columns("subjects")}
            original = None
            if legacy:
                metadata = MetaData()
                metadata.reflect(bind=connection, only=[Profile.__tablename__, *[model.__tablename__ for model in COLLECTIONS.values()]])
                if engine.dialect.name == "postgresql":
                    connection.exec_driver_sql("LOCK TABLE profile, subjects, plans, study_logs, review_items, review_attempts IN ACCESS EXCLUSIVE MODE")
                profile = connection.execute(select(metadata.tables["profile"])).mappings().one()
                original = canonical({"format": "zhian-backup", "version": 1, "exported_date": today(), "profile": dict(profile),
                                      **{key: [dict(row) for row in connection.execute(select(metadata.tables[model.__tablename__])).mappings()]
                                         for key, model in COLLECTIONS.items()}})
                # Persist the file before dropping legacy tables. Metadata is registered below.
                with Session(bind=connection, join_transaction_mode="rollback_only") as session:
                    # snapshot() needs the new metadata; create only its supporting tables first.
                    Account.__table__.create(connection, checkfirst=True)
                    from .database import BackupSnapshot
                    BackupSnapshot.__table__.create(connection, checkfirst=True)
                    session.add(Account(id=LOCAL_ACCOUNT))
                    session.flush()
                    snapshot(session, LOCAL_ACCOUNT, original, directory, "before-upgrade")
                    session.flush()
                for model in DELETE_ORDER:
                    metadata.tables[model.__tablename__].drop(connection)
            Base.metadata.create_all(connection)
            with Session(bind=connection, join_transaction_mode="rollback_only") as session:
                if session.get(Account, LOCAL_ACCOUNT) is None:
                    session.add(Account(id=LOCAL_ACCOUNT))
                    session.flush()
                if original:
                    from .backups import replace_data
                    replace_data(session, LOCAL_ACCOUNT, original)
                seed(session)
                session.flush()
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
