import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

async def main():
    api_id = int(input("API_ID: ").strip())
    api_hash = input("API_HASH: ").strip()
    cliente = TelegramClient(StringSession(), api_id, api_hash)
    await cliente.start()
    print("\nCOPIE A CHAVE ABAIXO E COLE NO GITHUB COMO TELEGRAM_SESSAO:\n")
    print(cliente.session.save())
    await cliente.disconnect()

asyncio.run(main())
