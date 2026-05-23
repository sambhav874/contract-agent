import asyncio
from app.db.mongodb import MongoDB

async def main():
    await MongoDB.connect()
    chunks = await MongoDB.get_chunks('LOG-2024-V3-PROD')
    if chunks:
        # Sort by char_start
        macro = [c for c in chunks if c.get('chunk_level') == 'macro']
        macro.sort(key=lambda x: x.get('char_start', 0))
        print("Macro chunks count:", len(macro))
        for m in macro[:5]:
            print(f"[{m.get('char_start')}-{m.get('char_end')}] len={len(m.get('text',''))} id={m.get('chunk_id')}")
    else:
        print("No chunks")
    await MongoDB.close()

asyncio.run(main())
