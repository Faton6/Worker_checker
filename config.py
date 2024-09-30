'''
Пример для разных баз данных:

SQLite (файл базы данных в текущей директории):

arduino
Copy code
DATABASE_URL=sqlite:///database.db
PostgreSQL:

bash
Copy code
DATABASE_URL=postgresql://username:password@localhost:5432/database_name
MySQL:

bash
Copy code
DATABASE_URL=mysql://username:password@localhost:3306/database_name
'''
# config.py
import os
from dotenv import load_dotenv

# Загрузка переменных окружения из файла .env
load_dotenv()

# Токен вашего Telegram бота
BOT_TOKEN = os.getenv("BOT_TOKEN")

# URL для подключения к базе данных
DATABASE_URL = os.getenv("DATABASE_URL")

# Время в минутах, через которое необходимо напомнить о непроставленном статусе
REMINDER_TIME = 10