import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.llm.gemini_client import call_gemini

async def main():
    print(f"Gemini Analysis Model from settings: {settings.gemini_analysis_model}")
    print(f"Gemini Fast Model from settings: {settings.gemini_fast_model}")

    try:
        print("Calling Gemini model...")
        response = await call_gemini(
            model=settings.gemini_analysis_model,
            system_prompt="You are a helpful assistant.",
            user_message="Hello, please respond with a JSON object containing a key 'message' with value 'hello'.",
            response_schema={"type": "OBJECT", "properties": {"message": {"type": "STRING"}}, "required": ["message"]},
        )
        print("Response:", response)
    except Exception as e:
        print("Error calling Gemini model:", e)

if __name__ == "__main__":
    asyncio.run(main())
