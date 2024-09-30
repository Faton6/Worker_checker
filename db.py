'''
Пояснения по коду:

Импорт необходимых модулей:

databases для асинхронной работы с базой данных.
sqlalchemy и его компоненты для определения схемы базы данных и построения запросов.
DATABASE_URL из файла config.py для подключения к базе данных.
date из модуля datetime для работы с датами.
Определение схемы базы данных:

Таблица users:
telegram_id — уникальный идентификатор пользователя в Telegram, первичный ключ.
full_name — полное имя пользователя.
is_admin — флаг, указывающий, является ли пользователь администратором.
Таблица statuses:
id — уникальный идентификатор записи, первичный ключ.
telegram_id — идентификатор пользователя, внешний ключ к таблице users.
status — статус пользователя на конкретную дату.
description — дополнительное описание статуса, если выбрано "Другое".
date — дата, на которую установлен статус.
Класс Database:

Инициализация:
Создает подключение к базе данных и инициализирует схему.
Методы для подключения и отключения от базы данных:
connect и disconnect — устанавливают и разрывают соединение с базой данных.
Методы для работы с пользователями:
add_user — добавляет нового пользователя.
get_user — получает информацию о пользователе.
set_admin — устанавливает или снимает права администратора.
get_admins — получает список всех администраторов.
get_all_users — получает список всех пользователей.
Методы для работы со статусами:
add_status — добавляет новый статус для пользователя на текущую дату.
get_status — получает статус пользователя на текущую дату.
get_statuses_for_date — получает все статусы на заданную дату.
check_status_exists — проверяет наличие статуса у пользователя на заданную дату.
update_status — обновляет существующий статус пользователя.
Важно:

Асинхронные операции:

Все методы взаимодействия с базой данных являются асинхронными (async def), что позволяет эффективно работать с большим количеством запросов без блокировки основного потока.
Использование metadata.create_all(self.engine):

При инициализации класса Database создаются все таблицы в базе данных, если они еще не существуют.
Безопасность и корректность данных:

Поля таблиц имеют ограничения nullable=False, где это необходимо, чтобы обеспечить целостность данных.
Настройка базы данных:

DATABASE_URL:
Убедитесь, что в файле config.py правильно указан параметр DATABASE_URL, соответствующий вашей базе данных (например, PostgreSQL, SQLite и т.д.).
Пример для SQLite: DATABASE_URL = "sqlite:///database.db"
Установка зависимостей:

Для работы с базой данных необходимо установить следующие пакеты:
bash
Copy code
pip install databases[sqlite] sqlalchemy
Замените sqlite на соответствующий драйвер вашей базы данных, если используете другую СУБД.
'''
# db.py
import databases
import sqlalchemy
from sqlalchemy import (
    Column, Integer, String, Boolean, Date, MetaData, Table, create_engine, and_
)
from config import DATABASE_URL
from datetime import datetime
import pytz

metadata = MetaData()

# Определение таблицы пользователей
users = Table(
    'users', metadata,
    Column('telegram_id', Integer, primary_key=True),
    Column('full_name', String, nullable=False),
    Column('is_admin', Boolean, default=False),
)

# Определение таблицы статусов
statuses = Table(
    'statuses', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('telegram_id', Integer, nullable=False),
    Column('status', String, nullable=False),
    Column('description', String, nullable=True),
    Column('date', Date, nullable=False),
)

class Database:
    def __init__(self):
        self.database = databases.Database(DATABASE_URL)
        self.engine = create_engine(DATABASE_URL)
        metadata.create_all(self.engine)
        self.timezone = pytz.timezone('Europe/Moscow')  # Укажите вашу таймзону

    async def connect(self):
        await self.database.connect()

    async def disconnect(self):
        await self.database.disconnect()

    # Методы для работы с пользователями

    async def add_user(self, telegram_id: int, full_name: str):
        """
        Добавляет нового пользователя в базу данных.
        """
        query = users.insert().values(
            telegram_id=telegram_id,
            full_name=full_name,
            is_admin=False
        )
        await self.database.execute(query)

    async def delete_user(self, telegram_id: int):
        """
        Удаляет пользователя из базы данных.
        """
        query = users.delete().where(users.c.telegram_id == telegram_id)
        await self.database.execute(query)
        # Также удаляем все статусы пользователя
        query = statuses.delete().where(statuses.c.telegram_id == telegram_id)
        await self.database.execute(query)

    async def get_user(self, telegram_id: int):
        """
        Получает информацию о пользователе по его Telegram ID.
        """
        query = users.select().where(users.c.telegram_id == telegram_id)
        return await self.database.fetch_one(query)

    async def set_admin(self, telegram_id: int, is_admin: bool):
        """
        Устанавливает или снимает права администратора у пользователя.
        """
        query = users.update().where(
            users.c.telegram_id == telegram_id
        ).values(is_admin=is_admin)
        await self.database.execute(query)

    async def get_admins(self):
        """
        Возвращает список всех администраторов.
        """
        query = users.select().where(users.c.is_admin == True)
        return await self.database.fetch_all(query)

    async def get_all_users(self):
        """
        Возвращает список всех пользователей.
        """
        query = users.select()
        return await self.database.fetch_all(query)

    # Методы для работы со статусами

    async def add_or_update_status(self, telegram_id: int, status: str, description: str = None):
        """
        Добавляет или обновляет статус пользователя на текущую дату.
        """
        today = datetime.now(self.timezone).date()
        if await self.check_status_exists(telegram_id, today):
            await self.update_status(telegram_id, status, description)
        else:
            await self.add_status(telegram_id, status, description)

    async def add_status(self, telegram_id: int, status: str, description: str = None):
        """
        Добавляет новый статус для пользователя на текущую дату.
        """
        today = datetime.now(self.timezone).date()
        query = statuses.insert().values(
            telegram_id=telegram_id,
            status=status,
            description=description,
            date=today
        )
        await self.database.execute(query)

    async def get_status(self, telegram_id: int, date_):
        """
        Получает статус пользователя на указанную дату.
        """
        query = statuses.select().where(
            statuses.c.telegram_id == telegram_id,
            statuses.c.date == date_
        )
        return await self.database.fetch_one(query)

    async def get_statuses_for_date(self, date_):
        """
        Возвращает все статусы сотрудников на заданную дату.
        """
        query = statuses.select().where(statuses.c.date == date_)
        return await self.database.fetch_all(query)

    async def get_statuses_in_period(self, start_date, end_date):
        """
        Возвращает все статусы сотрудников за указанный период.
        """
        query = statuses.select().where(
            statuses.c.date.between(start_date, end_date)
        )
        return await self.database.fetch_all(query)

    async def check_status_exists(self, telegram_id: int, date_):
        """
        Проверяет, существует ли статус у пользователя на заданную дату.
        """
        query = statuses.select().where(
            statuses.c.telegram_id == telegram_id,
            statuses.c.date == date_
        )
        status = await self.database.fetch_one(query)
        return status is not None

    async def update_status(self, telegram_id: int, status: str, description: str = None):
        """
        Обновляет статус пользователя на текущую дату.
        """
        today = datetime.now(self.timezone).date()
        query = statuses.update().where(
            statuses.c.telegram_id == telegram_id,
            statuses.c.date == today
        ).values(
            status=status,
            description=description
        )
        await self.database.execute(query)
