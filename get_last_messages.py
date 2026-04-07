from telethon import TelegramClient

api_id = 38573702
api_hash = "d9d60a5689656529b3e23a21d3553a65"

client = TelegramClient("session", api_id, api_hash)

async def main():
    channel_id = -1001402220998  # replace with yours

    messages = await client.get_messages(channel_id, limit=10)

    for msg in messages:
        print(msg.text)

with client:
    client.loop.run_until_complete(main())