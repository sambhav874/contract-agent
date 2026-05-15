import asyncio
from app.db.mongodb import MongoDB

async def main():
    await MongoDB.connect()
    db = MongoDB()
    kpis = await db.get_kpis("airport_agreement_2025")
    print("\n".join([f"{k.get('id')}: {k.get('name')}" for k in kpis]))
    await MongoDB.close()

if __name__ == "__main__":
    asyncio.run(main())
