"""Rode uma vez só para ligar o robô à sua conta do Telegram.

O Telegram manda um código no seu app; digite aqui quando pedir.
No fim aparece uma chave longa: copie e cole no GitHub como TELEGRAM_SESSAO.
"""
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = int(input("API_ID: ").strip())
api_hash = input("API_HASH: ").strip()
with TelegramClient(StringSession(), api_id, api_hash) as cliente:
    print("\nCOPIE A CHAVE ABAIXO E COLE NO GITHUB COMO TELEGRAM_SESSAO:\n")
    print(cliente.session.save())
