'''
Пояснения по коду:

is_admin декоратор:

Проверяет, является ли пользователь администратором, перед выполнением обработчика.
Если пользователь не администратор, отправляет сообщение о недостаточности прав.
format_status_report функция:

Форматирует текстовый отчет по статусам сотрудников.
Используется для отправки отчета администраторам.
При необходимости добавляет пояснение к статусу "Другое".
notify_admins функция:

Отправляет указанное сообщение всем администраторам.
Используется для уведомления администраторов о неответивших сотрудниках и других событиях.
get_user_full_name функция:

Получает полное имя пользователя по его Telegram ID.
Если пользователь не найден, возвращает строку "Неизвестный пользователь".
Примечания:

Импорт необходимых модулей и классов:

wraps из модуля functools для сохранения метаданных функции при использовании декораторов.
types из библиотеки aiogram для работы с типами сообщений.
Database из файла db.py для взаимодействия с базой данных.
Использование асинхронных функций:

Все функции, которые взаимодействуют с базой данных или ботом, являются асинхронными (async def).
Обеспечение переиспользования кода:

Функции format_status_report и notify_admins помогают избежать дублирования кода в обработчиках и планировщиках.
Важно:

Убедитесь, что файл utils.py находится в одной директории с другими файлами проекта (handlers.py, db.py, config.py, main.py).
Проверьте корректность импортов во всех файлах, чтобы избежать ошибок во время выполнения.
Перед запуском бота убедитесь, что все зависимости установлены, и настроены необходимые параметры в config.py.
'''

# utils.py
from functools import wraps
from aiogram import types
from db import Database
from aiogram.utils.exceptions import ChatNotFound
import logging

def is_admin(db: Database):
    """
    Декоратор для проверки прав администратора у пользователя.
    """
    def decorator(handler):
        @wraps(handler)
        async def wrapper(message: types.Message, *args, **kwargs):
            user = await db.get_user(message.from_user.id)
            if user and user['is_admin']:
                return await handler(message, *args, **kwargs)
            else:
                await message.reply("У вас нет прав администратора.")
        return wrapper
    return decorator

def format_status_report(users, statuses):
    """
    Форматирует отчет по статусам сотрудников для отправки администратору.
    """
    report = ""
    status_dict = {status['telegram_id']: status for status in statuses}
    for user in users:
        user_id = user['telegram_id']
        if user_id in status_dict:
            status = status_dict[user_id]['status']
            description = status_dict[user_id]['description']
            if status == "Другое" and description:
                status += f" ({description})"
        else:
            status = "Другое (На уточнении)"
        report += f"{user['full_name']}: {status}\n"
    return report

async def notify_admins(dp, db: Database, message_text: str):
    """
    Уведомляет всех администраторов указанным сообщением.
    """
    admins = await db.get_admins()
    for admin in admins:
        try:
            await dp.bot.send_message(
                chat_id=admin['telegram_id'],
                text=message_text,
                parse_mode='Markdown'
            )
        except ChatNotFound:
            logging.error(f"Чат с администратором {admin['telegram_id']} не найден.")

async def get_user_full_name(db: Database, telegram_id: int):
    """
    Получает полное имя пользователя по его Telegram ID.
    """
    user = await db.get_user(telegram_id)
    if user:
        return user['full_name']
    return "Неизвестный пользователь"



