import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

async def check_noprefix():
    client = AsyncIOMotorClient(Config.MONGODB_URI)
    db = client["musicBot"]
    
    users = await db["noprefix"].find().to_list(None)
    print(f"Total no-prefix users: {len(users)}")
    for user in users:
        print(f"  User ID: {user['user_id']}")
    
    client.close()

asyncio.run(check_noprefix())
