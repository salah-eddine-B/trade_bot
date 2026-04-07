from telethon import TelegramClient, events

api_id = 38573702
api_hash = "d9d60a5689656529b3e23a21d3553a65"

client = TelegramClient("session", api_id, api_hash)

@client.on(events.NewMessage(chats='-1001402220998'))
async def handler(event):
    print("Signal received:", event.message.message)

client.start()
print("Listening to messages...")
client.run_until_disconnected()