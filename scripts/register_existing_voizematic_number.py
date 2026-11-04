import asyncio

from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.db.models.voice_number import VoiceNumber

USER_ID = 1  # Replace with your actual platform user ID
PHONE_NUMBER = "+912269982608"  # Your already-purchased number
PROVIDER_NUMBER_ID = "YOUR_ACTUAL_VOIZEMATIC_NUMBER_ID"


async def main():
    async with AsyncSessionLocal() as db:
        existing = await db.scalar(
            select(VoiceNumber).where(
                VoiceNumber.provider == "voizematic",
                VoiceNumber.phone_number == PHONE_NUMBER,
            )
        )

        if existing:
            print("Number is already registered:", existing.id)
            return

        number = VoiceNumber(
            user_id=USER_ID,
            phone_number=PHONE_NUMBER,
            provider="voizematic",
            provider_number_id=PROVIDER_NUMBER_ID,
            is_active=True,
        )

        db.add(number)
        await db.commit()
        await db.refresh(number)

        print("Registered number ID:", number.id)


if __name__ == "__main__":
    asyncio.run(main())
