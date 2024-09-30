'''
Пояснения по коду:

Импорт необходимых модулей и классов:

asyncio для запуска асинхронного цикла событий.
logging для настройки логирования.
Bot, Dispatcher, BotCommand из библиотеки aiogram для работы с ботом.
MemoryStorage из aiogram.contrib.fsm_storage.memory для хранения состояний FSM в памяти.
AsyncIOScheduler из apscheduler.schedulers.asyncio для планирования задач.
Database из файла db.py для взаимодействия с базой данных.
register_handlers из файла handlers.py для регистрации обработчиков команд и сообщений.
BOT_TOKEN из файла config.py для доступа к токену бота.
Настройка логирования:

Устанавливается уровень логирования на INFO для вывода информации о работе бота.
Функция main:

Инициализация бота и диспетчера:
Создается экземпляр Bot с использованием токена из config.py.
Создается экземпляр Dispatcher с передачей бота и хранилища состояний MemoryStorage.
Инициализация базы данных:
Создается экземпляр Database и устанавливается соединение с базой данных.
Инициализация планировщика:
Создается экземпляр AsyncIOScheduler и запускается.
Регистрация обработчиков:
Вызывается функция register_handlers, которая регистрирует все обработчики и планировщики задач, передавая диспетчер, базу данных и планировщик.
Установка команд бота:
Устанавливаются команды бота, которые будут отображаться в интерфейсе Telegram:
/start — регистрация в системе.
/status — проверка или изменение статуса.
/admin — панель администратора.
Запуск бота:
Запускается метод start_polling для начала приема и обработки обновлений от Telegram.
Обработка завершения работы:
В блоке finally происходит корректное закрытие сессии бота и отключение от базы данных.
Точка входа в приложение:

Проверка if __name__ == "__main__" гарантирует, что функция main будет выполнена только при непосредственном запуске файла main.py.
asyncio.run(main()) запускает асинхронную функцию main в событийном цикле.
'''
# main.py
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import BotCommand
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz
from db import Database
from handlers import register_handlers
from config import BOT_TOKEN, DATABASE_URL


logging.basicConfig(level=logging.INFO) # change to INFO

async def main():
    if not BOT_TOKEN:
        logging.error("Не указан токен бота. Пожалуйста, установите переменную BOT_TOKEN в файле .env")
        exit(1)

    if not DATABASE_URL:
        logging.error("Не указан URL базы данных. Пожалуйста, установите переменную DATABASE_URL в файле .env")
        exit(1)
    # Инициализация бота и диспетчера
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(bot, storage=MemoryStorage())

    # Инициализация базы данных
    db = Database()
    await db.connect()

    # Установка таймзоны
    timezone = pytz.timezone('Europe/Moscow')  # Укажите вашу таймзону

    # Инициализация планировщика с таймзоной
    scheduler = AsyncIOScheduler(timezone=timezone)
    scheduler.start()

    # Регистрация обработчиков
    register_handlers(dp, db, scheduler)

    # Установка команд бота
    await bot.set_my_commands([
        BotCommand(command="/start", description="Регистрация в системе"),
        BotCommand(command="/status", description="Проверить или изменить статус"),
        BotCommand(command="/admin", description="Панель администратора"),
        BotCommand(command="/help", description="Справка по командам"),
        BotCommand(command="/delete_me", description="Удалить свою регистрацию"),
    ])

    # Запуск бота
    try:
        await dp.start_polling()
    finally:
        # Корректное завершение работы
        await bot.session.close()
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
    