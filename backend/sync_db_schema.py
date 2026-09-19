import asyncio
from sqlalchemy import text
from app.core.database import AsyncSessionLocal, engine
from app.models.base import Base
# Import all models so metadata is populated
from app.models import user, scan, product, violation, compliance_ledger, re_inspection_ticket, inspection_history, citizen_notification

async def inspect_and_sync():
    async with AsyncSessionLocal() as session:
        # Check tables
        res = await session.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public';
        """))
        tables = [t[0] for t in res.fetchall()]
        print("Existing tables:", tables)

        # Check missing columns in scans
        res = await session.execute(text("""
            SELECT column_name FROM information_schema.columns WHERE table_name = 'scans';
        """))
        scan_cols = [c[0] for c in res.fetchall()]
        print("Scans columns:", scan_cols)

        if "source" not in scan_cols:
            print("Adding scans.source column...")
            await session.execute(text("ALTER TABLE scans ADD COLUMN source VARCHAR(50) NOT NULL DEFAULT 'inspector';"))
        
        if "claimed_violation_type" not in scan_cols:
            print("Adding scans.claimed_violation_type column...")
            await session.execute(text("ALTER TABLE scans ADD COLUMN claimed_violation_type VARCHAR(100);"))

        # Check users table
        res = await session.execute(text("""
            SELECT column_name FROM information_schema.columns WHERE table_name = 'users';
        """))
        user_cols = [c[0] for c in res.fetchall()]
        print("Users columns:", user_cols)

        if "xp" not in user_cols:
            print("Adding users.xp column...")
            await session.execute(text("ALTER TABLE users ADD COLUMN xp INTEGER NOT NULL DEFAULT 100;"))

        # Commit changes
        await session.commit()
        print("Database schema migration completed successfully!")

    # Also run create_all in case any tables like citizen_notifications don't exist yet
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Base.metadata.create_all completed!")

if __name__ == "__main__":
    asyncio.run(inspect_and_sync())
