import requests
import json
import sqlite3
import psycopg2
import urllib.parse
import telebot
from telebot import types
from datetime import datetime
import re
import os
from flask import Flask, request
import traceback
from psycopg2 import sql


TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

DATABASE_URL = os.getenv("DATABASE_URL").replace("postgres://", "postgresql://")

conn = psycopg2.connect(DATABASE_URL)
print("✅ Подключение успешно")
conn.close()

WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = f"https://familybudgetbot-production.up.railway.app{WEBHOOK_PATH}"

app = Flask(__name__)


@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    print('in @app.route')
    return '', 200


class ConvertionException(Exception):
    pass


class MyCustomException(Exception):
    pass


categories = {
    'еда': ('food', 'продукты', 'продукты'),
    'бытовая химия': ('household_chemicals', 'бытовую химию', 'бытовая химия'),
    'бытовой инвентарь': ('household_equipment', 'бытовой инвентарь', 'бытовой инвентарь'),
    'мебель': ('furniture', 'мебель', 'мебель'),
    'посуда': ('dishes', 'посуда', 'посуда'),
    'домашний декор': ('cosiness', 'домашний декор', 'домашний декор'),
    'канцтовары': ('stationery', 'канцтовары', 'канцтовары'),
    'детский сад/школа': ('school', 'детский сад/школа', 'детский сад/школа'),
    'одежда': ('clothes', 'одежду', 'одежда'),
    'украшения/аксессуары': ('accessories', 'украшения/аксессуары', 'украшения/аксессуары'),
    'спорт': ('sport', 'спорт', 'спорт'),
    'хобби': ('hobby', 'хобби', 'хобби'),
    'рестораны/кафе': ('eating_out', 'рестораны/кафе', 'рестораны/кафе'),
    'путешествия': ('trips', 'путешествия', 'путешествия'),
    'развлечения': ('events', 'развлечения', 'развлечения'),
    'косметика/уходовые процедуры': ('cosmetic', 'косметику/уходовые процедуры', 'косметика/уходовые процедуры'),
    'здоровье': ('health', 'здоровье', 'здоровье'),
    'домашние животные': ('pets', 'домашние животные', 'домашние животные'),
    'техника': ('technic', 'технику', 'техника'),
    'аренда': ('rent', 'аренду квартиры', 'аренда квартиры'),
    'ипотека': ('mortgage', 'ипотека', 'ипотека'),
    'ремонт': ('repair', 'ремонт', 'ремонт'),
    'коммуналка': ('communal_apartment', 'коммуналку', 'коммуналка'),
    'оплата счетов': ('payment_of_bills', 'оплата счетов', 'оплата счетов'),
    'кредиты/долги': ('loans_debts', 'кредиты/долги', 'кредиты/долги'),
}


def categories_buttons():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(
        types.KeyboardButton('еда'), types.KeyboardButton('бытовая химия'),
        types.KeyboardButton('бытовой инвентарь'), types.KeyboardButton('мебель'),
        types.KeyboardButton('посуда'), types.KeyboardButton('домашний декор'),
        types.KeyboardButton('канцтовары'), types.KeyboardButton('детский сад/школа'),
        types.KeyboardButton('одежда'), types.KeyboardButton('украшения/аксессуары'),
        types.KeyboardButton('спорт'), types.KeyboardButton('хобби'),
        types.KeyboardButton('рестораны/кафе'), types.KeyboardButton('путешествия'),
        types.KeyboardButton('развлечения'), types.KeyboardButton('косметика/уходовые процедуры'),
        types.KeyboardButton('здоровье'), types.KeyboardButton('домашние животные'),
        types.KeyboardButton('техника'), types.KeyboardButton('аренда'),
        types.KeyboardButton('ипотека'), types.KeyboardButton('ремонт'),
        types.KeyboardButton('коммуналка'), types.KeyboardButton('оплата счетов'),
        types.KeyboardButton('кредиты/долги'), types.KeyboardButton('Вернуться в главное меню')
    )
    return markup


def days_declension(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return 'день'
    elif n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return 'дня'
    else:
        return 'дней'


def get_single_users():
    connection = psycopg2.connect(DATABASE_URL)
    cursor = connection.cursor()
    cursor.execute('SELECT single_users.name FROM single_users')
    users = cursor.fetchall()
    connection.close()
    single_users = [user[0] for user in users]
    return single_users


def get_family_users():
    connection = psycopg2.connect(DATABASE_URL)
    cursor = connection.cursor()
    cursor.execute('SELECT family_users.name FROM family_users')
    users = cursor.fetchall()
    connection.close()
    family_users = [user[0] for user in users]
    return family_users


def get_code_words():
    connection = psycopg2.connect(DATABASE_URL)
    cursor = connection.cursor()
    cursor.execute('SELECT log_in_to_family.code_word FROM log_in_to_family')
    code_words = cursor.fetchall()
    connection.close()
    code_words = [code_word[0] for code_word in code_words]
    return code_words


def get_passwords(code_word):
    connection = psycopg2.connect(DATABASE_URL)
    cursor = connection.cursor()
    cursor.execute('SELECT log_in_to_family.password FROM log_in_to_family WHERE code_word=%s',
                   (code_word, ))
    passwords = cursor.fetchall()
    connection.close()
    password = [password[0] for password in passwords]
    return password


def add_single_users_in_database(name):
    connection = psycopg2.connect(DATABASE_URL)
    cursor = connection.cursor()
    cursor.execute(
        f'INSERT INTO single_users ("name") VALUES (%s)', (name, ))
    connection.commit()
    connection.close()


def add_expenses_to_database(amount, table_name, user):
    today = datetime.now().date().isoformat()  # '2025-08-27'
    connection = psycopg2.connect(DATABASE_URL)
    cursor = connection.cursor()
    cursor.execute(f'INSERT INTO {table_name} ("name", cost, "date") VALUES (%s, %s, %s)',
                   (user, amount, today))
    connection.commit()
    connection.close()


def get_expenses_in_one_category(category, category_text, username):
    # answer = get_expenses_in_one_category(table_name, message.text, username)
    single_users = get_single_users()

    if username in single_users:
        connection = psycopg2.connect(DATABASE_URL)
        cursor = connection.cursor()
        
        cursor.execute(f'SELECT COUNT(DISTINCT "date") FROM {category} WHERE "name"=%s', (username,))
        count_of_days = cursor.fetchall()[0][0]
        connection.close()

        if count_of_days == 0:
            return 'Вы ещё не заполняли эту статью расходов :)'

        elif 0 < count_of_days < 60:
            day = days_declension(count_of_days)
            connection = psycopg2.connect(DATABASE_URL)
            cursor = connection.cursor()
            cursor.execute(f'''SELECT SUM(cost::int) FROM {category} WHERE TO_DATE("date", 'YYYY-MM-DD') >= 
            CURRENT_DATE - INTERVAL '59 days' AND "name"=%s''', (username, ))
            result = cursor.fetchall()[0][0]
            connection.close()
            average_amount = int(result) / int(count_of_days)
            return (f'Вы ведёте бюджет *в категории "{category_text}" {count_of_days} {day}*.\n\nБот пока не может '
                    f'показать вам статистику по месяцам: для этого нужно вести бюджет хотя бы 60 дней :)\n\nПокажу '
                    f'то, что есть сейчас:\nза *{count_of_days} {day} на категорию "{category_text}" потрачено '
                    f'{result}* 💸\n*средние расходы в день - {average_amount}* 💸')

        elif count_of_days == 60:
            day = days_declension(count_of_days)

            connection = psycopg2.connect(DATABASE_URL)
            cursor = connection.cursor()
            cursor.execute(f'''SELECT SUM(cost::int) FROM {category} WHERE TO_DATE("date", 'YYYY-MM-DD') >= 
                        CURRENT_DATE - INTERVAL '60 days' AND "name"=%s''', (username,))
            all_days = cursor.fetchall()[0][0]
            connection.close()

            connection = psycopg2.connect(DATABASE_URL)
            cursor = connection.cursor()
            cursor.execute(f'''SELECT SUM(cost::int) FROM {category} WHERE TO_DATE("date", 'YYYY-MM-DD') >= 
                        CURRENT_DATE - INTERVAL '30 days' AND "name"=%s''', (username,))
            last_30_days = cursor.fetchall()[0][0]
            conn.close()

            first_30_days = int(all_days) - int(last_30_days)

            if first_30_days > last_30_days:
                average_amount = int(all_days) / int(count_of_days)
                difference = int(first_30_days) - int(last_30_days)
                return (f'Вы ведёте бюджет *в категории "{category_text}" {count_of_days} {day}*.\n*Всего потрачено '
                        f'{all_days}* 💸, средние расходы в день - *{average_amount}* 💸\n\nВ первые 30 дней '
                        f'вы потратили *{first_30_days}* 💸\nВ последние 30 дней вы потратили *{last_30_days}* 💸\n'
                        f'*В первые 30 дней вы потратили на {difference} больше, чем в последние 30 дней*:)')
            elif first_30_days < last_30_days:
                average_amount = int(all_days) / int(count_of_days)
                difference = int(last_30_days) - int(first_30_days)
                return (f'Вы ведёте бюджет *в категории "{category_text}" {count_of_days} {day}*.\n*Всего потрачено '
                        f'{all_days}* 💸, средние расходы в день - *{average_amount}* 💸\n\nВ первые 30 дней '
                        f'вы потратили *{first_30_days}* 💸\nВ последние 30 дней вы потратили *{last_30_days}* 💸\n'
                        f'*В последние 30 дней вы потратили на {difference} больше, чем в первые 30 дней*:)')

        elif count_of_days > 60:
            pass
            # day = days_declension(count_of_days)
            #
            # connection = psycopg2.connect(DATABASE_URL)
            # cursor = connection.cursor()
            # cursor.execute(f'''SELECT SUM(cost::int) FROM {category} WHERE TO_DATE("date", 'YYYY-MM-DD') >=
            #                         CURRENT_DATE - INTERVAL '60 days' AND "name"=%s''', (username,))
            # all_days = cursor.fetchall()[0][0]
            # connection.close()
            #
            # connection = psycopg2.connect(DATABASE_URL)
            # cursor = connection.cursor()
            # cursor.execute(f'''SELECT SUM(cost::int) FROM {category} WHERE TO_DATE("date", 'YYYY-MM-DD') >=
            #                         CURRENT_DATE - INTERVAL '30 days' AND "name"=%s''', (username,))
            # last_30_days = cursor.fetchall()[0][0]
            # conn.close()
            #
            # first_30_days = int(all_days) - int(last_30_days)
            #
            # if first_30_days > last_30_days:
            #     average_amount = int(all_days) / int(count_of_days)
            #     difference = int(first_30_days) - int(last_30_days)
            #     return (f'Вы ведёте бюджет *в категории "{category_text}" {count_of_days} {day}*.\n*Всего потрачено '
            #             f'{all_days}* 💸, средние расходы в день - *{average_amount}* 💸\n\nВ первые 30 дней '
            #             f'вы потратили *{first_30_days}* 💸\nВ последние 30 дней вы потратили *{last_30_days}* 💸\n'
            #             f'*В первые 30 дней вы потратили на {difference} больше, чем в последние 30 дней*:)')

    else:
        print('else')
        connection = psycopg2.connect(DATABASE_URL)
        cursor = connection.cursor()
        cursor.execute('SELECT family_users.family_number FROM family_users WHERE "name"=%s', (username,))
        family_number = cursor.fetchall()[0][0]
        connection.close()

        connection = psycopg2.connect(DATABASE_URL)
        cursor = connection.cursor()
        cursor.execute('SELECT family_users.name FROM family_users WHERE family_number=%s',
                       (family_number,))
        family = cursor.fetchall()
        family = [name[0] for name in family]
        connection.close()

        all_days = []
        total_amount = 0

        for name in family:
            print(f'name = {name}')
            connection = psycopg2.connect(DATABASE_URL)
            cursor = connection.cursor()
            cursor.execute(f'SELECT (MAX("date") - MIN("date")) + 1 FROM {category} WHERE "name"=%s',
                           (name,))
            # count_of_days_one_name = cursor.fetchall()
            count_of_days_one_name = cursor.fetchall()[0]
            print(f'count_of_days_one_name = {count_of_days_one_name}')
            all_days.append(count_of_days_one_name)
            print(f'all_days = {all_days}')
            connection.close()

            if count_of_days_one_name != 0:
                print('if count_of_days_one_name != 0:')

                connection = psycopg2.connect(DATABASE_URL)
                cursor = connection.cursor()
                cursor.execute(f'''SELECT COALESCE(SUM(cost::int), 0) FROM {category} 
                WHERE "name"=%s''', (name, ))
                result = cursor.fetchone()[0]
                total_amount += result
                connection.close()

        if len(all_days) != 0 and total_amount != 0:
            max_days = max(all_days)
            day = days_declension(max_days)
            average_amount = int(total_amount) / int(max_days)
            return (f'Ваша семья ведёт бюджет *в категории "{category_text}" {max_days} {day}*.\n\nЗа *{max_days} '
                    f'{day} на категорию "{category_text}" потрачено {total_amount}* 💸\n*средние расходы в день '
                    f'- {average_amount}* 💸')
        else:
            return 'Ваша семья ещё не заполняла эту статью расходов :)'


def get_expenses_in_one_month(username):
    single_users = get_single_users()
    if username in single_users:
        all_data = ''
        all_amount = 0
        for category in categories:
            table = categories.get(category)[0]
            word = categories.get(category)[2]
            connection = psycopg2.connect(DATABASE_URL)
            cursor = connection.cursor()
            cursor.execute(f'SELECT "name" FROM {table}')
            names = cursor.fetchall()
            connection.close()
            names = list(set([name[0] for name in names]))
            if username in names:
                connection = psycopg2.connect(DATABASE_URL)
                cursor = connection.cursor()
                # cursor.execute(f'''SELECT SUM(cost::int) FROM {table} WHERE TO_DATE("date", 'YYYY-MM-DD') >=
                # CURRENT_DATE - INTERVAL '30 days' AND "name"=%s''', (username, ))

                query = sql.SQL('''SELECT SUM(cost::int) FROM {table} WHERE TO_DATE("date", 'YYYY-MM-DD') 
                                    >= CURRENT_DATE - INTERVAL '30 days' AND "name" = %s''').format(
                    table=sql.Identifier(table))
                cursor.execute(query, (username,))

                amount = cursor.fetchall()[0][0]
                connection.close()

                all_amount += int(amount)
                # connection = psycopg2.connect(DATABASE_URL)
                # cursor = connection.cursor()
                # cursor.execute(f'''SELECT COUNT(DISTINCT "date") FROM {table} WHERE TO_DATE("date", 'YYYY-MM-DD')
                # >= CURRENT_DATE - INTERVAL '30 days' AND "name"=%s''', (username, ))
                # count_of_days = cursor.fetchall()[0][0]
                # connection.close()
                # average_amount = int(amount) / int(count_of_days)
                average_amount = int(amount) / 30
                text = (f'*{word.upper()}:*\nза последний месяц потрачено - *{amount}* 💸\n'
                        f'средние расходы в день - *{average_amount}* 💸\n\n')
                all_data += text

        if all_amount != 0:
            all_data += f'*{all_amount} - ОБЩАЯ СУММА, ПОТРАЧЕННАЯ ЗА МЕСЯЦ*\n😳'
            return all_data
        else:
            return 'Вы ничего не вносили в свой бюджет последние 30 дней:)'

    else:
        connection = psycopg2.connect(DATABASE_URL)
        cursor = connection.cursor()
        cursor.execute('SELECT family_users.family_number FROM family_users WHERE "name"=%s', (username,))
        family_number = cursor.fetchall()[0][0]
        connection.close()

        connection = psycopg2.connect(DATABASE_URL)
        cursor = connection.cursor()
        cursor.execute('SELECT family_users.name FROM family_users WHERE family_number=%s',
                       (family_number,))
        family = cursor.fetchall()
        family = [name[0] for name in family]
        print(f'family = {family}')
        connection.close()

        all_data = ''
        all_amount = 0

        for category in categories:
            table = categories.get(category)[0]
            word = categories.get(category)[2]
            connection = psycopg2.connect(DATABASE_URL)
            cursor = connection.cursor()
            cursor.execute(f'SELECT "name" FROM {table}')
            names = cursor.fetchall()
            connection.close()
            names = list(set([name[0] for name in names]))

            amount_category = 0
            days_category = []

            for name in family:
                if name in names:
                    connection = psycopg2.connect(DATABASE_URL)
                    cursor = connection.cursor()

                    query = sql.SQL('''SELECT SUM(cost::int) FROM {table} WHERE TO_DATE("date", 'YYYY-MM-DD') 
                    >= CURRENT_DATE - INTERVAL '30 days' AND "name" = %s''').format(table=sql.Identifier(table))
                    cursor.execute(query, (name,))

                    # cursor.execute(f'''SELECT SUM(cost::int) FROM {table} WHERE TO_DATE("date", 'YYYY-MM-DD') >=
                    # CURRENT_DATE - INTERVAL '30 days' AND "name"=%s''', (name, ))  то что было

                    amount = cursor.fetchall()[0][0]
                    print(f'amount = {amount}')
                    connection.close()

                    if amount is not None:
                        amount_category += int(amount)

                    connection = psycopg2.connect(DATABASE_URL)
                    cursor = connection.cursor()
                    cursor.execute(f'''SELECT "date" FROM {table} WHERE TO_DATE("date", 'YYYY-MM-DD') >= 
                    CURRENT_DATE - INTERVAL '30 days' AND "name"=%s''', (name, ))

                    all_days_one_name = cursor.fetchall()
                    connection.close()
                    all_days_one_name = [date[0] for date in all_days_one_name]

                    for day in all_days_one_name:
                        days_category.append(day)

            days_category = len(set(days_category))
            if days_category != 0:
                # average_amount = int(amount_category) / int(days_category)
                average_amount = int(amount_category) / 30
                text = (f'*{word.upper()}:*\nза последний месяц потрачено - *{amount_category}* 💸\n'
                        f'средние расходы в день - *{average_amount}* 💸\n\n')

                all_data += text
                print(f'all_data = {all_data}')
                all_amount += amount_category
                print(f'all_amount = {all_amount}')

        if all_amount != 0:
            all_data += f'*{all_amount} - ОБЩАЯ СУММА, ПОТРАЧЕННАЯ ЗА МЕСЯЦ*\n😳'
            print(f'all_data = {all_data}')
            return all_data
        else:
            return 'Ваша семья ничего не вносила в ваш бюджет последние 30 дней:)'


def start_family_in_database(text, column_name, name):
    if column_name == 'code_word':
        connection = psycopg2.connect(DATABASE_URL)
        cursor = connection.cursor()
        cursor.execute(f'INSERT INTO log_in_to_family ("name", code_word, "password", family_number) '
                       f'VALUES (%s, %s, %s, %s)', (name, text, 0, 0))
        connection.commit()
        connection.close()

        connection = psycopg2.connect(DATABASE_URL)
        cursor = connection.cursor()
        cursor.execute('SELECT log_in_to_family.id FROM log_in_to_family')
        id_names = cursor.fetchall()
        id_names = [id_name[0] for id_name in id_names]
        id_names.sort()
        last_id = id_names[-1]
        connection.close()

        connection = psycopg2.connect(DATABASE_URL)
        cursor = connection.cursor()
        cursor.execute(f'INSERT INTO family_users ("name", family_number) VALUES (%s, %s)',
                       (name, last_id))
        cursor.execute(f'UPDATE log_in_to_family SET family_number=%s WHERE family_number=%s AND "name"=%s',
                       (last_id, 0, name))
        connection.commit()
        connection.close()

    elif column_name == 'password':
        connection = psycopg2.connect(DATABASE_URL)
        cursor = connection.cursor()
        cursor.execute(f'UPDATE log_in_to_family SET "password"=%s WHERE "password"=%s AND "name"=%s',
                       (text, 0, name))
        connection.commit()
        connection.close()


def add_family_in_database(username, password):
    connection = psycopg2.connect(DATABASE_URL)
    cursor = connection.cursor()
    cursor.execute(
        'SELECT log_in_to_family.family_number FROM log_in_to_family WHERE "password"=%s', (password, ))
    family_number = cursor.fetchall()[0][0]
    connection.close()

    connection = psycopg2.connect(DATABASE_URL)
    cursor = connection.cursor()
    cursor.execute(f'INSERT INTO family_users (name, family_number) VALUES (%s, %s)',
                   (username, family_number))
    connection.commit()
    connection.close()


@bot.message_handler(commands=['start', ])
def start(message: telebot.types.Message):
    if message.chat.type == 'private':
        username = message.from_user.username
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        single_users = get_single_users()
        family_users = get_family_users()

        if username in single_users or username in family_users:
            markup.add(types.KeyboardButton('Добавить расходы'), types.KeyboardButton('Посмотреть расходы'))
            bot.send_message(message.chat.id, text="Привет, {0.first_name}! Решите, что будете делать "
                                                   ":)".format(message.from_user), reply_markup=markup)
            bot.register_next_step_handler(message, actions)

        else:
            markup.add(types.KeyboardButton('Семейный'), types.KeyboardButton('Одиночный'))
            bot.send_message(message.chat.id, text='Привет, {0.first_name}! Начнём! 😌\nДля начала решите, как '
                                                   'вы будете заполнять бюджет: в одиночку или всей семьёй '
                                                   ':)'.format(message.from_user),
                             reply_markup=markup)
            bot.register_next_step_handler(message, family_or_single)


@bot.message_handler(content_types=['text', ])
def family_or_single(message):
    if message.chat.type == 'private':
        username = message.from_user.username
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        if type(message.text) is str:

            if message.text == '/start' or message.text == 'Вернуться в главное меню':
                start(message)

            elif message.text == 'Семейный':
                markup.add(types.KeyboardButton('Присоединиться к чату с семейным бюджетом'),
                           types.KeyboardButton('Начать чат с семейным бюджетом'),
                           types.KeyboardButton('Вернуться в главное меню'))
                bot.send_message(message.chat.id, text='Вы хотите присоединиться к чату с семейным бюджетом или только '
                                                       'хотите завести чат с бюджетом?\nВыберите нужное :)',
                                 reply_markup=markup)
                bot.register_next_step_handler(message, actions_with_family_budget)

            elif message.text == 'Одиночный':
                add_single_users_in_database(username)
                buttons = categories_buttons()
                bot.send_message(message.chat.id, text='Выберите категорию, которую хотите заполнить :)',
                                 reply_markup=buttons)
                bot.register_next_step_handler(message, choose_category)

            else:
                markup.add(types.KeyboardButton('Семейный'), types.KeyboardButton('Одиночный'))
                bot.send_message(message.chat.id,
                                 text='Не надо ничего вводить😌\nПросто выберите один из вариантов, '
                                      'представленных ниже :)'.format(message.from_user), reply_markup=markup)
                bot.register_next_step_handler(message, family_or_single)
        else:
            markup.add(types.KeyboardButton('Семейный'), types.KeyboardButton('Одиночный'))
            bot.send_message(message.chat.id,
                             text='Вы шлете картинки или доки 😌\nВыберите один из вариантов, представленных '
                                  'ниже :)'.format(message.from_user), reply_markup=markup)
            bot.register_next_step_handler(message, family_or_single)


def actions_with_family_budget(message):
    if message.chat.type == 'private':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        if type(message.text) is str:

            if message.text == '/start' or message.text == 'Вернуться в главное меню':
                start(message)

            elif message.text == 'Присоединиться к чату с семейным бюджетом':
                bot.send_message(message.chat.id, text='Введите кодовое слово :)', reply_markup=markup)
                bot.register_next_step_handler(message, enter_code_word)

            elif message.text == 'Начать чат с семейным бюджетом':
                markup.add(types.KeyboardButton('Вернуться в главное меню'))
                bot.send_message(message.chat.id, text='Придумайте название/кодовое слово/словосочетание, под которым '
                                                       'вы будете входить в чат с ботом :)\nСкажите это '
                                                       'название/кодовое слово/словосочетание членам вашей семьи, '
                                                       'чтобы они также смогли войти и внести данные в семейный '
                                                       'бюджет 😌\nНапример: *"Гуси щипают детей"/хрюшки-хитрюшки*\n'
                                                       'Всё это нужно только для первого входа в чат с бюджетом: '
                                                       'после бот зафиксирует пользователя и больше не будет '
                                                       'спрашивать :)\nИли вернитесь в главное меню :)',
                                 reply_markup=markup, parse_mode='Markdown')
                bot.register_next_step_handler(message, start_family, 'code_word',
                                               'название/кодовое слово/словосочетание',
                                               '"Гуси щипают детей"/хрюшки-хитрюшки"', 'Название')

            else:
                markup.add(types.KeyboardButton('Присоединиться к чату с семейным бюджетом'),
                           types.KeyboardButton('Начать чат с семейным бюджетом'),
                           types.KeyboardButton('Вернуться в главное меню'))
                bot.send_message(message.chat.id,
                                 text='Не надо ничего вводить😌')
                bot.send_message(message.chat.id, text='Вы хотите присоединиться к чату с семейным бюджетом или только '
                                                       'хотите завести чат с бюджетом?\nВыберите нужное :)',
                                 reply_markup=markup)
                bot.register_next_step_handler(message, actions_with_family_budget)
        else:
            markup.add(types.KeyboardButton('Присоединиться к чату с семейным бюджетом'),
                       types.KeyboardButton('Начать чат с семейным бюджетом'),
                       types.KeyboardButton('Вернуться в главное меню'))
            bot.send_message(message.chat.id,
                             text='Вы шлете картинки или доки 😌')
            bot.send_message(message.chat.id, text='Вы хотите присоединиться к чату с семейным бюджетом или только '
                                                   'хотите завести чат с бюджетом?\nВыберите нужное :)',
                             reply_markup=markup)
            bot.register_next_step_handler(message, actions_with_family_budget)


def actions(message):
    if message.chat.type == 'private':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        if type(message.text) is str:

            if message.text == '/start' or message.text == 'Вернуться в главное меню':
                start(message)

            elif message.text == 'Добавить расходы':
                buttons = categories_buttons()
                bot.send_message(message.chat.id, text='Выберите категорию :)', reply_markup=buttons)
                bot.register_next_step_handler(message, choose_category)

            elif message.text == 'Посмотреть расходы':
                markup.add(types.KeyboardButton('Посмотреть расходы за последние 30 дней'),
                           types.KeyboardButton('Посмотреть расходы в отдельной категории'),
                           types.KeyboardButton('Посмотреть расходы за конкретный месяц'),
                           )
                bot.send_message(message.chat.id, text='Выберите, что хотите посмотреть :)', reply_markup=markup)
                bot.register_next_step_handler(message, view_expenses)

            else:
                markup.add(types.KeyboardButton('Добавить расходы'), types.KeyboardButton('Посмотреть расходы'))
                bot.send_message(message.chat.id,
                                 text='Не надо ничего вводить😌\nПросто выберите один из вариантов, '
                                      'представленных ниже :)'.format(message.from_user), reply_markup=markup)
                bot.register_next_step_handler(message, actions)
        else:
            markup.add(types.KeyboardButton('Добавить расходы'), types.KeyboardButton('Посмотреть расходы'))
            bot.send_message(message.chat.id,
                             text='Вы шлете картинки или доки 😌\nВыберите один из вариантов, представленных '
                                  'ниже :)'.format(message.from_user), reply_markup=markup)
            bot.register_next_step_handler(message, actions)


def start_family(message, column_name, text, example, code_word_or_password):
    username = message.from_user.username
    if message.chat.type == 'private':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        if type(message.text) is str:

            if message.text == '/start' or message.text == 'Вернуться в главное меню':
                start(message)

            else:
                if code_word_or_password == 'Название':
                    start_family_in_database(message.text, column_name, username)
                    markup.add(types.KeyboardButton('Вернуться в главное меню'))
                    answer = (f'{code_word_or_password} для входа в семейный бюджет добавлено ✅\nОсталось немного :)'
                              f'\nПридумайте цифровой пароль для входа и введите его сюда :)\nНапример: *1223* :)')
                    bot.send_message(message.chat.id, text=answer, parse_mode='Markdown')
                    bot.register_next_step_handler(message, start_family, 'password', 'цифровой пароль',
                                                   '"34556"', 'Пароль')

                elif code_word_or_password == 'Пароль':
                    if message.text.isdigit():
                        start_family_in_database(message.text, column_name, username)
                        answer = f'{code_word_or_password} для входа в семейный бюджет добавлен ✅'
                        bot.send_message(message.chat.id, text=answer)
                        buttons = categories_buttons()
                        bot.send_message(message.chat.id, text='Выберите категорию :)', reply_markup=buttons)
                        bot.register_next_step_handler(message, choose_category)
                    else:
                        markup.add(types.KeyboardButton('Вернуться в главное меню'))
                        bot.send_message(message.chat.id,
                                         text=f'Что-то не так с введённым паролем 😔\n*{message.text}*\n'
                                              f'Введите ещё раз цифровой пароль :)\nНапример: *1223* :)',
                                         parse_mode='Markdown', reply_markup=markup)
                        bot.register_next_step_handler(message, start_family, 'password', 'цифровой пароль',
                                                       '"34556"', 'Пароль')

        else:
            markup.add(types.KeyboardButton('Вернуться в главное меню'))
            bot.send_message(message.chat.id, text='Вы шлете картинки или доки 😌')
            bot.send_message(message.chat.id, text=f'Придумайте {text}, под которым вы будете входить в чат с ботом '
                                                   f':)\nСкажите это {text} членам вашей семьи, чтобы они также '
                                                   f'смогли войти и внести данные в семейный бюджет 😌\n'
                                                   f'Например: *{example}\n'
                                                   'Всё это нужно только для первого входа в бюджет: после бот '
                                                   'зафиксирует пользователя и больше не будет спрашивать :)\n'
                                                   'Или вернитесь в главное меню :)',
                             reply_markup=markup, parse_mode='Markdown')
            bot.register_next_step_handler(message, start_family, column_name, text, example)


def enter_code_word(message):
    if message.chat.type == 'private':
        code_words = get_code_words()
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        if type(message.text) is str:

            if message.text == '/start' or message.text == 'Вернуться в главное меню':
                start(message)

            elif message.text in code_words:
                markup.add(types.KeyboardButton('Вернуться в главное меню'))
                bot.send_message(message.chat.id, text=f'Правильно! Введите пароль :)', reply_markup=markup)
                bot.register_next_step_handler(message, enter_password, message.text)

            else:
                markup.add(types.KeyboardButton('Вернуться в главное меню'))
                bot.send_message(message.chat.id, text=f'Введенное вами кодовое слово неверно {message.text} 😔'
                                                       f'\nВведите ещё раз :)', reply_markup=markup)
                bot.register_next_step_handler(message, enter_code_word)
        else:
            markup.add(types.KeyboardButton('Вернуться в главное меню'))
            bot.send_message(message.chat.id, text='Вы шлете картинки или доки 😌')
            bot.send_message(message.chat.id, text='Введите кодовое слово :)', reply_markup=markup)
            bot.register_next_step_handler(message, enter_code_word)


def enter_password(message, code_word):
    if message.chat.type == 'private':
        username = message.from_user.username
        passwords = get_passwords(code_word)
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        if type(message.text) is str:

            if message.text == '/start' or message.text == 'Вернуться в главное меню':
                start(message)

            elif int(message.text) in passwords:
                add_family_in_database(username, message.text)
                markup.add(types.KeyboardButton('Добавить расходы'), types.KeyboardButton('Посмотреть расходы'))
                bot.send_message(message.chat.id, text='Готово ✅\nВы присоединились к ведению семейного бюджета :)'
                                                       '\nВыберите, что хотите сделать :)', reply_markup=markup)
                bot.register_next_step_handler(message, actions)

            else:
                markup.add(types.KeyboardButton('Вернуться в главное меню'))
                bot.send_message(message.chat.id, text=f'Вы ввели неправильный пароль {message.text} 😔'
                                                       f'\nВведите ещё раз :)', reply_markup=markup)
                bot.register_next_step_handler(message, enter_password, code_word)
        else:
            markup.add(types.KeyboardButton('Вернуться в главное меню'))
            bot.send_message(message.chat.id, text='Вы шлете картинки или доки 😌')
            bot.send_message(message.chat.id, text='Введите пароль :)', reply_markup=markup)
            bot.register_next_step_handler(message, enter_password, code_word)


def choose_category(message):
    if message.chat.type == 'private':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        if type(message.text) is str:

            if message.text == '/start' or message.text == 'Вернуться в главное меню':
                start(message)

            elif message.text in categories:
                table_name = categories.get(message.text)[0]
                word = categories.get(message.text)[1]
                markup.add(types.KeyboardButton('Вернуться в главное меню'))
                bot.send_message(message.chat.id, text='Внесите сумму в виде числа)\n*Например, "3000" :)*',
                                 reply_markup=markup, parse_mode='Markdown')
                bot.register_next_step_handler(message, add_expenses, table_name, word)

            else:
                buttons = categories_buttons()
                bot.send_message(message.chat.id, text='Не надо ничего вводить 😌\nПросто выберите категорию '
                                                       ':)'.format(message.from_user), reply_markup=buttons)
                bot.register_next_step_handler(message, choose_category)

        else:
            buttons = categories_buttons()
            bot.send_message(message.chat.id,
                             text='Вы шлете картинки или доки 😌\nПросто выберите категорию '
                                  ':)'.format(message.from_user), reply_markup=buttons)
            bot.register_next_step_handler(message, choose_category)


def add_expenses(message, table_name, word):
    if message.chat.type == 'private':
        username = message.from_user.username
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        if type(message.text) is str:

            if message.text == '/start' or message.text == 'Вернуться в главное меню':
                start(message)

            else:
                data = ''
                for elem in message.text:
                    if elem != ' ':
                        data += elem

                if data.isdigit():
                    if data != '0':
                        add_expenses_to_database(data, table_name, username)
                        bot.send_message(message.chat.id, text=f'*Сумма, потраченная на {word}, внесена 🔥*',
                                         parse_mode='Markdown')
                        markup.add(types.KeyboardButton('Добавить расходы'),
                                   types.KeyboardButton('Посмотреть расходы'))
                        bot.send_message(message.chat.id, text='Решите, что будете делать :)', reply_markup=markup)
                        bot.register_next_step_handler(message, actions)
                    else:
                        markup.add(types.KeyboardButton('Вернуться в главное меню'))
                        bot.send_message(message.chat.id, text=f'Вы ввели "0" 😌\nЕсли вы ничего не потратили, то не '
                                                               f'надо ничего вводить :)\nЕсли вы ошиблись, введя "0", '
                                                               f'то введите ещё раз сумму, потраченную на {word} в '
                                                               f'виде числа :)\nНапример: 500\nИли вернитесь '
                                                               f'в главное меню :)', reply_markup=markup)
                        bot.register_next_step_handler(message, add_expenses, table_name, word, )
                else:
                    markup.add(types.KeyboardButton('Вернуться в главное меню'))
                    bot.send_message(message.chat.id, text=f'Что-то не так с введёнными данными '
                                                           f'<{message.text}> 😶\nВведите ещё раз сумму, потраченную '
                                                           f'на {word} в виде числа :)\nНапример: 500\nИли вернитесь '
                                                           f'в главное меню :)', reply_markup=markup)
                    bot.register_next_step_handler(message, add_expenses, table_name, word, )
        else:
            markup.add(types.KeyboardButton('Вернуться в главное меню'))
            bot.send_message(message.chat.id, text=f'Вы шлете картинки или доки 😌\nПросто введите сумму, '
                                                   f'потраченную на {word} в виде числа :)\nИли вернитесь в главное '
                                                   f'меню :)', reply_markup=markup)
            bot.register_next_step_handler(message, add_expenses, table_name, word)


def view_expenses(message):
    if message.chat.type == 'private':
        username = message.from_user.username
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        if type(message.text) is str:

            if message.text == '/start' or message.text == 'Вернуться в главное меню':
                start(message)

            elif message.text == 'Посмотреть расходы за последние 30 дней':
                answer = get_expenses_in_one_month(username)
                markup.add(types.KeyboardButton('Вернуться в главное меню'))
                bot.send_message(message.chat.id, text=answer, reply_markup=markup, parse_mode='Markdown')
                bot.register_next_step_handler(message, actions)

            elif message.text == 'Посмотреть расходы в отдельной категории':
                buttons = categories_buttons()
                bot.send_message(message.chat.id,
                                 text='Выберите категорию 😌'.format(message.from_user), reply_markup=buttons)
                bot.register_next_step_handler(message, view_expenses_in_one_category)

            elif message.text == 'Посмотреть расходы за конкретный месяц':
                pass
                # buttons = categories_buttons()
                # bot.send_message(message.chat.id,
                #                  text='Выберите категорию 😌'.format(message.from_user), reply_markup=buttons)
                # bot.register_next_step_handler(message, view_expenses_in_one_category)

            else:
                markup.add(types.KeyboardButton('Посмотреть расходы за последние 30 дней'),
                           types.KeyboardButton('Посмотреть расходы в отдельной категории'))
                bot.send_message(message.chat.id,
                                 text='Не надо ничего вводить 😌\nПросто выберите один из вариантов, '
                                      'представленных ниже :)'.format(message.from_user), reply_markup=markup)
                bot.register_next_step_handler(message, view_expenses)

        else:
            markup.add(types.KeyboardButton('Посмотреть расходы за последние 30 дней'),
                       types.KeyboardButton('Посмотреть расходы в отдельной категории'))
            bot.send_message(message.chat.id,
                             text='Вы шлете картинки или доки 😌\nВыберите один из вариантов, представленных '
                                  'ниже :)'.format(message.from_user), reply_markup=markup)
            bot.register_next_step_handler(message, view_expenses)


def view_expenses_in_one_category(message):
    if message.chat.type == 'private':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        username = message.from_user.username
        if type(message.text) is str:

            if message.text == '/start' or message.text == 'Вернуться в главное меню':
                start(message)

            elif message.text in categories:
                print('elif message.text in categories:')
                table_name = categories.get(message.text)[0]
                print(f'table_name = {table_name}')
                answer = get_expenses_in_one_category(table_name, message.text, username)
                markup.add(types.KeyboardButton('Вернуться в главное меню'))
                bot.send_message(message.chat.id, text=answer, reply_markup=markup, parse_mode='Markdown')
                bot.register_next_step_handler(message, actions)

            else:
                buttons = categories_buttons()
                bot.send_message(message.chat.id,
                                 text='Не надо ничего вводить 😌\nВыберите категорию, расходы на которую '
                                      'хотите посмотреть :)'.format(message.from_user), reply_markup=buttons)
                bot.register_next_step_handler(message, view_expenses_in_one_category)

        else:
            buttons = categories_buttons()
            bot.send_message(message.chat.id,
                             text='Вы шлете картинки или доки 😌\nВыберите категорию, расходы на которую '
                                  'хотите посмотреть :)'.format(message.from_user), reply_markup=buttons)
            bot.register_next_step_handler(message, view_expenses_in_one_category)


if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
