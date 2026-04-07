from telethon import TelegramClient

api_id = 38573702
api_hash = "d9d60a5689656529b3e23a21d3553a65"

client = TelegramClient("session", api_id, api_hash)

async def main():
    dialogs = await client.get_dialogs()

    for dialog in dialogs:
        print(dialog.name, dialog.id)

with client:
    client.loop.run_until_complete(main())