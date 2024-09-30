'''
Пояснения по коду:

Импорт необходимых модулей и классов:

Dispatcher, types, FSMContext, StatesGroup и другие из библиотеки aiogram.
Database из файла db.py.
is_admin из файла utils.py.
date из модуля datetime.
Определение классов состояний FSM:

Registration для регистрации пользователя.
AddAdmin и RemoveAdmin для добавления и удаления администратора.
OtherStatus для обработки статуса "Другое" с пояснением.
Функция register_handlers:

Регистрирует все обработчики команд и сообщений.
Настраивает планировщик задач scheduler.
Обработчики команд:

/start — регистрация нового пользователя.
/status — проверка и изменение статуса сотрудника.
/admin — доступ к панели администратора.
Обработчики состояний FSM:

process_full_name — обработка ввода ФИО при регистрации.
process_add_admin — обработка добавления нового администратора.
process_remove_admin — обработка удаления администратора.
process_other_status — обработка пояснения к статусу "Другое".
Обработчики CallbackQuery:

admin_menu_callback — обработка действий в панели администратора.
status_callback — обработка выбора статуса сотрудником.
Функции для планировщика задач:

send_status_request_scheduled — отправка запроса статусов сотрудникам в 8:00.
check_unanswered_statuses — проверка неответивших сотрудников в 8:45.
Вспомогательные функции:

send_status_request_to_user — отправка запроса статуса конкретному сотруднику.
send_admin_report — формирование и отправка отчета администраторам.
check_employee_statuses — получение текущей статистики по статусам сотрудников.
Важно:

Убедитесь, что все зависимости установлены, включая aiogram, APScheduler и другие необходимые библиотеки.
Проверьте корректность импортов и соответствие имен файлов (например, db.py, utils.py).
Перед запуском бота необходимо настроить базу данных и указать правильный BOT_TOKEN и DATABASE_URL в файле config.py.
'''
# handlers.py
from aiogram import Dispatcher, types
from aiogram.dispatcher.filters import Text
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, InputFile
)
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from apscheduler.triggers.cron import CronTrigger
import config
from db import Database
from utils import is_admin, format_status_report, notify_admins, get_user_full_name
from datetime import datetime, timedelta
import pytz
import io
import xlsxwriter
import logging

DJANGO_CELERY_BEAT_TZ_AWARE = False


# Состояния для FSM
class Registration(StatesGroup):
    full_name = State()


class AddAdmin(StatesGroup):
    admin_id = State()


class RemoveAdmin(StatesGroup):
    admin_id = State()


class OtherStatus(StatesGroup):
    description = State()


class SendMessage(StatesGroup):
    message_text = State()


class DeleteConfirmation(StatesGroup):
    confirm = State()


class ReportDate(StatesGroup):
    date = State()


class ScheduleChange(StatesGroup):
    time = State()


timezone = pytz.timezone('Europe/Moscow')


def register_handlers(dp: Dispatcher, db: Database, scheduler):
    @dp.message_handler(commands=['start'])
    async def cmd_start(message: types.Message):
        user = await db.get_user(message.from_user.id)
        if user:
            await message.reply("Вы уже зарегистрированы.")
        else:
            await message.reply(
                "Добро пожаловать! Пожалуйста, введите ваше полное ФИО для регистрации в системе."
            )
            await Registration.full_name.set()

    @dp.message_handler(state=Registration.full_name)
    async def process_full_name(message: types.Message, state: FSMContext):
        full_name = message.text.strip()
        await db.add_user(message.from_user.id, full_name)
        await message.reply(
            f"Спасибо, {full_name}! Вы успешно зарегистрированы.\n"
            "Используйте команду /help для получения списка доступных команд."
        )
        await state.finish()
        # Отправляем приветственное сообщение
        await message.reply(
            "Добро пожаловать! Этот бот поможет вам сообщать о вашем статусе каждый день."
        )

    @dp.message_handler(commands=['help'])
    async def cmd_help(message: types.Message):
        help_text = (
            "/start - Регистрация в системе\n"
            "/status - Проверить или изменить статус\n"
            "/admin - Панель администратора\n"
            "/help - Показать это сообщение\n"
            "/delete_me - Удалить свою регистрацию"
        )
        await message.reply(help_text)

    @dp.message_handler(commands=['delete_me'])
    async def cmd_delete_me(message: types.Message):
        await message.reply(
            "Вы уверены, что хотите удалить свою регистрацию? Это действие необратимо. Введите 'Да', чтобы подтвердить, или 'Нет', чтобы отменить.")
        await DeleteConfirmation.confirm.set()

    @dp.message_handler(state=DeleteConfirmation.confirm)
    async def process_delete_confirmation(message: types.Message, state: FSMContext):
        confirmation = message.text.strip().lower()
        if confirmation == 'да':
            await db.delete_user(message.from_user.id)
            await message.reply("Ваша регистрация удалена.")
        else:
            await message.reply("Отмена удаления регистрации.")
        await state.finish()

    @dp.message_handler(commands=['status'])
    async def cmd_status(message: types.Message):
        user = await db.get_user(message.from_user.id)
        if not user:
            await message.reply(
                "Вы не зарегистрированы. Пожалуйста, используйте /start для регистрации."
            )
            return
        await send_status_request_to_user(dp, message.from_user.id)

    @dp.message_handler(commands=['admin'])
    @is_admin(db)
    async def cmd_admin(message: types.Message):
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(
                "Получить статистику", callback_data="admin_get_stats"
            ),
            InlineKeyboardButton(
                "Проверить статус сотрудников",
                callback_data="admin_check_statuses"
            )
        )
        keyboard.add(
            InlineKeyboardButton(
                "Добавить администратора", callback_data="admin_add_admin"
            ),
            InlineKeyboardButton(
                "Удалить администратора", callback_data="admin_remove_admin"
            )
        )
        keyboard.add(
            InlineKeyboardButton(
                "Отправить сообщение всем", callback_data="admin_send_message"
            ),
            InlineKeyboardButton(
                "Изменить расписание", callback_data="admin_change_schedule"
            )
        )
        keyboard.add(
            InlineKeyboardButton(
                "Получить отчет за дату", callback_data="admin_get_stats_by_date"
            ),
            InlineKeyboardButton(
                "Получить аналитические данные", callback_data="admin_get_analytics"
            )
        )
        await message.reply("Выберите действие:", reply_markup=keyboard)

    @dp.callback_query_handler(Text(startswith="admin_"))
    async def admin_menu_callback(
            callback_query: CallbackQuery, state: FSMContext
    ):
        action = callback_query.data
        if action == "admin_get_stats":
            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton(
                    "Получить статистику за сегодня", callback_data="admin_today_report"
                )
            )
            keyboard.add(
                InlineKeyboardButton(
                    "Получить xlsx отчет со статистикой", callback_data="admin_xlsx_report"
                )
            )
            await callback_query.message.reply("Выберите опцию:", reply_markup=keyboard)
            await callback_query.answer()
        elif action == "admin_today_report":
            await send_admin_report_replay(callback_query.message, db)
            await callback_query.answer()
        elif action == "admin_xlsx_report":
            await send_admin_xlsx_report(callback_query.message, db)
            await callback_query.answer()
        elif action == "admin_check_statuses":
            # Отправляем submenu
            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton(
                    "Проверить статус всех сотрудников", callback_data="admin_check_all_statuses"
                )
            )
            keyboard.add(
                InlineKeyboardButton(
                    "Проверить статус конкретного сотрудника", callback_data="admin_check_specific_status"
                )
            )
            await callback_query.message.reply("Выберите опцию:", reply_markup=keyboard)
            await callback_query.answer()
        elif action == "admin_add_admin":
            await callback_query.message.reply(
                "Введите Telegram ID пользователя, которого хотите "
                "сделать администратором."
            )
            await AddAdmin.admin_id.set()
            await callback_query.answer()
        elif action == "admin_remove_admin":
            await callback_query.message.reply(
                "Введите Telegram ID администратора, которого хотите удалить."
            )
            await RemoveAdmin.admin_id.set()
            await callback_query.answer()
        elif action == "admin_send_message":
            await callback_query.message.reply(
                "Введите сообщение, которое вы хотите отправить всем сотрудникам."
            )
            await SendMessage.message_text.set()
            await callback_query.answer()
        elif action == "admin_change_schedule":
            await callback_query.message.reply(
                "Введите новое время отправки запросов в формате ЧЧ:ММ (24-часовой формат)."
            )
            await ScheduleChange.time.set()
            await callback_query.answer()
        elif action == "admin_get_stats_by_date":
            await callback_query.message.reply(
                "Введите дату в формате ГГГГ-ММ-ДД для получения отчета."
            )
            await ReportDate.date.set()
            await callback_query.answer()
        elif action == "admin_get_analytics":
            await send_analytics(callback_query.message, db)
            await callback_query.answer()
        elif action == "admin_check_all_statuses":
            await send_status_request_scheduled(dp, db)
            await callback_query.message.reply("Запрос статусов всех сотрудников отправлен.")
            await callback_query.answer()
        elif action == "admin_check_specific_status":
            users = await db.get_all_users()
            if not users:
                await callback_query.message.reply("Нет зарегистрированных сотрудников.")
                await callback_query.answer()
                return
            keyboard = InlineKeyboardMarkup(row_width=1)
            for user in users:
                keyboard.add(
                    InlineKeyboardButton(
                        user['full_name'],
                        callback_data=f"admin_select_employee_{user['telegram_id']}"
                    )
                )
            await callback_query.message.reply("Выберите сотрудника:", reply_markup=keyboard)
            await callback_query.answer()
        elif action.startswith("admin_select_employee_"):
            telegram_id = int(action.split("_")[-1])
            await send_status_request_to_user(dp, telegram_id)
            selected_user = await db.get_user(telegram_id)
            if selected_user:
                await callback_query.message.reply(
                    f"Запрос статуса отправлен сотруднику {selected_user['full_name']}."
                )
            else:
                await callback_query.message.reply("Сотрудник не найден.")
            await callback_query.answer()

    @dp.message_handler(state=AddAdmin.admin_id)
    async def process_add_admin(message: types.Message, state: FSMContext):
        try:
            new_admin_id = int(message.text.strip())
            user = await db.get_user(new_admin_id)
            if not user:
                await message.reply("Пользователь с этим ID не зарегистрирован.")
            else:
                await db.set_admin(new_admin_id, True)
                await message.reply(
                    "Пользователь успешно назначен администратором."
                )
        except ValueError:
            await message.reply("Некорректный ID. Попробуйте еще раз.")
        await state.finish()

    @dp.message_handler(state=RemoveAdmin.admin_id)
    async def process_remove_admin(message: types.Message, state: FSMContext):
        try:
            admin_id = int(message.text.strip())
            user = await db.get_user(admin_id)
            if not user:
                await message.reply("Пользователь с этим ID не зарегистрирован.")
            elif not user['is_admin']:
                await message.reply("Этот пользователь не является администратором.")
            else:
                await db.set_admin(admin_id, False)
                await message.reply("Администратор успешно удален.")
        except ValueError:
            await message.reply("Некорректный ID. Попробуйте еще раз.")
        await state.finish()

    @dp.message_handler(state=SendMessage.message_text)
    async def process_send_message(message: types.Message, state: FSMContext):
        text = message.text.strip()
        users = await db.get_all_users()
        for user in users:
            try:
                await dp.bot.send_message(
                    chat_id=user['telegram_id'],
                    text=f"Сообщение от администратора:\n\n{text}",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logging.error(f"Не удалось отправить сообщение пользователю {user['telegram_id']}: {e}")
        await message.reply("Сообщение отправлено всем сотрудникам.")
        await state.finish()

    @dp.message_handler(state=ScheduleChange.time)
    async def process_schedule_change(message: types.Message, state: FSMContext):
        time_text = message.text.strip()
        try:
            hour, minute = map(int, time_text.split(":"))
            # Обновление расписания в планировщике
            scheduler.reschedule_job('send_status_request_job', trigger='cron', hour=hour, minute=minute)
            scheduler.reschedule_job('send_reminders_job', trigger='cron', hour=hour,
                                     minute=minute - config.REMINDER_TIME)
            await message.reply(f"Время отправки запросов изменено на {hour:02d}:{minute:02d}.")
        except ValueError:
            await message.reply("Некорректный формат времени. Пожалуйста, введите в формате ЧЧ:ММ.")
        await state.finish()

    @dp.message_handler(state=ReportDate.date)
    async def process_report_date(message: types.Message, state: FSMContext):
        date_text = message.text.strip()
        try:
            report_date = datetime.strptime(date_text, "%Y-%m-%d").date()
            await send_admin_xlsx_report(message, db, report_date)
        except ValueError:
            await message.reply("Некорректный формат даты. Пожалуйста, введите в формате ГГГГ-ММ-ДД.")
        await state.finish()

    @dp.callback_query_handler(Text(startswith="status_"))
    async def status_callback(
            callback_query: CallbackQuery, state: FSMContext
    ):
        status_code = callback_query.data.split("_")[1]
        status_text = {
            "1": "Очно",
            "2": "Удаленно",
            "3": "Больничный",
            "4": "В отпуске",
            "5": "Другое"
        }
        status = status_text[status_code]
        if status_code == "5":
            await callback_query.message.reply(
                "Пожалуйста, уточните ваш статус."
            )
            await OtherStatus.description.set()
            # Оповещение администраторов
            full_name = await get_user_full_name(db, callback_query.from_user.id)
            await notify_admins(dp, db,
                                f"Сотрудник [{full_name}](tg://user?id={callback_query.from_user.id}) установил статус: {status}.")
            await callback_query.answer()
        else:
            await db.add_or_update_status(callback_query.from_user.id, status)
            await callback_query.message.reply(
                f"Ваш статус сохранен: {status}. Вы можете изменить его в любое время с помощью команды /status."
            )

            await callback_query.answer()

    @dp.message_handler(state=OtherStatus.description)
    async def process_other_status(message: types.Message, state: FSMContext):
        description = message.text.strip()
        await db.add_or_update_status(
            message.from_user.id, "Другое", description
        )
        await message.reply(
            "Ваш статус сохранен. Вы можете изменить его в любое время с помощью команды /status."
        )
        # Оповещение администраторов
        full_name = await get_user_full_name(db, message.from_user.id)
        await notify_admins(dp, db,
                            f"Сотрудник [{full_name}](tg://user?id={message.from_user.id}) установил статус: Другое ({description}).")
        await state.finish()

    requst_hour = 8
    start_requst_min = 30
    remind_requst_min = start_requst_min + config.REMINDER_TIME  # 40
    check_unanswered_statuses_min = remind_requst_min + 5  # 45
    send_admin_report_min = check_unanswered_statuses_min + 5 # 50

    # Планировщик задач
    scheduler.add_job(
        send_status_request_scheduled,
        trigger='cron',
        day_of_week='mon-fri',
        hour=requst_hour,
        minute=start_requst_min,
        args=(dp, db),
        id='send_status_request_job'
    )
    scheduler.add_job(
        send_reminders,
        trigger='cron',
        day_of_week='mon-fri',
        hour=requst_hour,
        minute=remind_requst_min,
        args=(dp, db),
        id='send_reminders_job'
    )
    scheduler.add_job(
        check_unanswered_statuses,
        trigger='cron',
        day_of_week='mon-fri',
        hour=requst_hour,
        minute=check_unanswered_statuses_min,
        args=(dp, db),
        id='check_unanswered_statuses_job'
    )
    scheduler.add_job(
        send_admin_report_dispatcher,
        trigger='cron',
        day_of_week='mon-fri',
        hour=requst_hour,
        minute=send_admin_report_min,
        args=(dp, db),
        id='send_admin_report_job'
    )


async def send_status_request_scheduled(dp: Dispatcher, db: Database):
    users = await db.get_all_users()
    for user in users:
        await send_status_request_to_user(dp, user['telegram_id'])


async def send_status_request_to_user(dp: Dispatcher, user_id: int):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("Очно", callback_data="status_1"),
        InlineKeyboardButton("Удаленно", callback_data="status_2")
    )
    keyboard.add(
        InlineKeyboardButton("Больничный", callback_data="status_3"),
        InlineKeyboardButton("В отпуске", callback_data="status_4"),
        InlineKeyboardButton("Другое", callback_data="status_5")
    )
    await dp.bot.send_message(
        chat_id=user_id,
        text="Пожалуйста, выберите ваш статус на сегодня:",
        reply_markup=keyboard
    )


async def send_reminders(dp: Dispatcher, db: Database):
    users = await db.get_all_users()
    today = datetime.now(timezone).date()
    for user in users:
        status = await db.get_status(user['telegram_id'], today)
        if not status:
            await dp.bot.send_message(
                chat_id=user['telegram_id'],
                text="Напоминаем, что вы еще не указали свой статус на сегодня. Пожалуйста, сделайте это до 9:00."
            )


async def send_admin_xlsx_report(message: types.Message, db: Database, report_date=None):
    if report_date is None:
        report_date = datetime.now(timezone).date()
    statuses = await db.get_statuses_for_date(report_date)
    users = {
        user['telegram_id']: user for user in await db.get_all_users()
    }
    report = format_status_report(users.values(), statuses)
    await message.reply(f"Отчет по статусам сотрудников на {report_date}:\n{report}")
    # Отправка отчета в Excel
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet()
    worksheet.write('A1', 'ФИО')
    worksheet.write('B1', 'Статус')
    worksheet.write('C1', 'Описание')
    row = 1
    for user_id, user in users.items():
        status = next(
            (s for s in statuses if s['telegram_id'] == user_id), None
        )
        status_text = status['status'] if status else "Не известно"
        description = status['description'] if status else "-"
        worksheet.write(row, 0, user['full_name'])
        worksheet.write(row, 1, status_text)
        worksheet.write(row, 2, description)
        row += 1
    workbook.close()
    output.seek(0)
    await message.reply_document(
        ('Отчет.xlsx', output),
        caption="Отчет по статусам сотрудников."
    )


async def send_admin_report(db: Database):
    report_date = datetime.now(timezone).date()
    statuses = await db.get_statuses_for_date(report_date)
    status_dict = {status['telegram_id']: status for status in statuses}
    users = {
        user['telegram_id']: user for user in await db.get_all_users()
    }
    res_stats = {'Очно': [], 'Удаленно': [], 'Больничный': [], 'В отпуске': [], 'Другое': [], 'Не известно': []}
    for user_id, user in users.items():
        if user_id in status_dict:
            status = status_dict[user_id]['status']
            description = status_dict[user_id]['description']
        else:
            status = "Не известно"

        print(user['full_name'])
        res_stats[status].append(user['full_name'].split()[0])
    

    report = (f'\nВ офисе: {len(res_stats["Очно"])}\nУдаленно: {len(res_stats["Удаленно"])} - {", ".join(res_stats["Удаленно"])}\nБольничный: {len(res_stats["Больничный"])} - {", ".join(res_stats["Больничный"])}\nВ отпуске: {len(res_stats["В отпуске"])} - {", ".join(res_stats["В отпуске"])}\nДругое: {len(res_stats["Другое"])} - {", ".join(res_stats["Другое"])}\nНе известно: {len(res_stats["Не известно"])} - {", ".join(res_stats["Не известно"])}')

    return report


async def send_admin_report_dispatcher(dp: Dispatcher, db: Database):
    report_date = datetime.now(timezone).date()
    report = await send_admin_report(db)

    admins = await db.get_admins()
    for admin in admins:
        admin_id = admin['telegram_id']
        try:
            await dp.bot.send_message(
                chat_id=admin_id,
                text=f"Отчет по статусам сотрудников на {report_date}:\n{report}"
            )
        except Exception as e:
            logging.error(f"Не удалось отправить отчет администратору {admin_id}: {e}")


async def send_admin_report_replay(message: types.Message, db: Database):
    report_date = datetime.now(timezone).date()
    report = await send_admin_report(db)
    admins = await db.get_admins()
    for admin in admins:
        admin_id = admin['telegram_id']
        try:
            await message.reply(f"Отчет по статусам сотрудников на {report_date}:\n{report}")
        except Exception as e:
            logging.error(f"Не удалось отправить отчет администратору {admin_id}: {e}")


async def check_unanswered_statuses(dp: Dispatcher, db: Database):
    users = await db.get_all_users()
    today = datetime.now(timezone).date()
    for user in users:
        status = await db.get_status(user['telegram_id'], today)
        if not status:
            await db.add_or_update_status(
                user['telegram_id'], "Не известно"
            )
            # Уведомление сотруднику
            await dp.bot.send_message(
                chat_id=user['telegram_id'],
                text="Вам автоматически присвоен статус 'Не известно', так как вы не ответили на запрос."
            )
            # Уведомление администраторам
            admins = await db.get_admins()
            for admin in admins:
                await dp.bot.send_message(
                    chat_id=admin['telegram_id'],
                    text=(
                        f"Сотрудник {user['full_name']} не ответил на запрос."
                        " Статус проставлен как 'Не известно'."  # Другое (На уточнении)
                    ),
                    parse_mode='Markdown'
                )


async def check_employee_statuses(message: types.Message, db: Database):
    await send_admin_xlsx_report(message, db)


async def send_analytics(message: types.Message, db: Database):
    # Пример простой аналитики за последний месяц
    end_date = datetime.now(timezone).date()
    start_date = end_date - timedelta(days=30)
    statuses = await db.get_statuses_in_period(start_date, end_date)
    # Анализ данных и формирование отчета
    report = "Аналитические данные за последний месяц:\n"
    status_counts = {}
    for status in statuses:
        status_text = status['status']
        status_counts[status_text] = status_counts.get(status_text, 0) + 1
    for status, count in status_counts.items():
        report += f"{status}: {count} раз(а)\n"
    await message.reply(report)
