from telethon import TelegramClient

api_id = 38573702
api_hash = "d9d60a5689656529b3e23a21d3553a65"

client = TelegramClient("session", api_id, api_hash)

client.start()
print("Connected to Telegram successfully!")

client.disconnect()