import asyncio
from app.db.mongodb import MongoDB

async def main():
    await MongoDB.connect()
    qas = await MongoDB.get_saved_qa('LOG-2024-V3-PROD')
    if qas:
        print("First QA sources:", qas[0].get("sources"))
    else:
        print("No QAs found")
    await MongoDB.close()

asyncio.run(main())
