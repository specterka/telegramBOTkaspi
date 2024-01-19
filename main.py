import logging
import csv
import requests
import time
from openpyxl import Workbook
from telegram import Update, Bot, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, ConversationHandler, MessageHandler, Filters

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Define states for the conversation
CHOOSING, TYPING_REPLY = range(2)


def get(city_id, _id):
    headers = {
        'Accept': 'application/json, text/*',
        'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json; charset=UTF-8',
        'Cookie': 'k_stat=ca3bad98-45a4-4139-aea3-f838d613af72; ks.tg=52; ssaid=f46561e0-9cd7-11ed-bb4d-ad3d1adf37c8; _ga=GA1.2.1160662921.1674668686; _ym_uid=1674668688623779345; _ym_d=1674668688; ks.ngs.s=e633617833b29aed2e06a1bb5b0d3d82; _hjSessionUser_283363=eyJpZCI6IjI2NmRjZjllLTVjNmMtNThiZi04ZmQyLTcwY2IzOTExODIzMiIsImNyZWF0ZWQiOjE2NzQ2Njg2ODU1NzAsImV4aXN0aW5nIjp0cnVlfQ==; _hjIncludedInSessionSample=1; _hjSession_283363=eyJpZCI6IjE2ZmI4NzU0LWEzZTUtNDE2My1iYjgyLWYyZmZlMzczZGZhNyIsImNyZWF0ZWQiOjE2NzUzNzQyODUzNTcsImluU2FtcGxlIjp0cnVlfQ==; _hjAbsoluteSessionInProgress=0; _gid=GA1.2.86683657.1675374286; _ym_isad=1; _ym_visorc=b; _gat_ddl=1; googtrans=/auto/en; googtrans=/auto/en; ks.cc=-1; kaspi.storefront.cookie.city=750000000; __tld__=null',
        'Origin': 'https://kaspi.kz',
        'Referer': 'https://kaspi.kz/shop/p/bosch-pointteq-2-608-577-351-nabor-19-sht--22700866/?c=750000000',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not_A Brand";v="99", "Google Chrome";v="109", "Chromium";v="109"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
    }

    json_data = {
        'cityId': city_id,
        'id': _id,
        'limit': 5,
        'page': 0
    }

    session = requests.Session()
    max_retries = 5
    for i in range(max_retries):
        try:
            response = session.post(f'https://kaspi.kz/yml/offer-view/offers/{_id}', headers=headers, json=json_data)
            response.raise_for_status()  # will throw an exception for error codes
            break
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            if i < max_retries - 1:
                wait_time = (i+1) * 2  # wait for 2, 4, 6, ... seconds
                print(f"Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)
            else:
                print("All attempts failed. Giving up.")
                return None  # or handle this in another way

    return response.json()


def parse_offers(row, writer):
    city_id = row["Ссылки"].split('?c=')[1]
    _id = row["Код каспи"]

    for idx, raw_offer in enumerate(get(city_id, _id)['offers']):
        offer = {}

        offer[f'Продавец_{idx+1}'] = raw_offer['merchantName']
        offer[f'Цена_{idx+1}'] = raw_offer['price']

        row.update(offer)

    writer.writerow(row)

# Updated scrape_data function with filtering
def scrape_data(filter_type=None, filter_value=None):
    with open('output_qural_top125.csv', encoding='utf-8-sig') as f:
        reader = list(csv.DictReader(f, delimiter=';'))
        fieldnames = list(reader[0].keys()) + ['Продавец_1', 'Цена_1', 'Продавец_2', 'Цена_2', 'Продавец_3', 'Цена_3',
                                               'Продавец_4', 'Цена_4', 'Продавец_5', 'Цена_5']

        with open('kaspi.csv', 'w', newline='', encoding='utf-8') as f2:
            writer = csv.DictWriter(f2, fieldnames=fieldnames)
            writer.writeheader()

            for row in reader:
                if filter_type and row[filter_type] != filter_value:
                    continue
                print(f'scraping {row["Ссылки"]}')
                parse_offers(row, writer)

    wb = Workbook()
    ws = wb.active
    with open('kaspi.csv', 'r', encoding='utf-8') as f:
        for row in csv.reader(f):
            ws.append(row)
    wb.save('kaspi_tiyn.xlsx')

# Function to start the conversation and ask the user's choice
def start(update: Update, context: CallbackContext):
    reply_keyboard = [['Бренд', 'Поставщик']]
    update.message.reply_text(
        "Привет! Как вы хотите сделать парсинг: по Бренду или по Поставщику?",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True),
    )
    return CHOOSING


# Function to extract unique values from a column
def get_unique_values(column_name):
    with open('output_qural_top125.csv', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        unique_values = set(row[column_name] for row in reader)
    return unique_values


# Function to handle the user's choice
def regular_choice(update: Update, context: CallbackContext):
    user_choice = update.message.text
    context.user_data['choice'] = user_choice
    unique_values = get_unique_values(user_choice)

    # Create a message with the unique values
    options_message = f"Выберите {user_choice} варианты:\n" + "\n".join(unique_values)
    update.message.reply_text(options_message)

    return TYPING_REPLY

# Function to skip filtering
def skip(update: Update, context: CallbackContext):
    update.message.reply_text('Делается парсинг на все товары.')
    scrape_data()  # Call scraping function without filtering
    update.message.reply_text('Парсинг закончился. Отправляю вам готовый файл')
    context.bot.send_document(chat_id=update.effective_chat.id, document=open('kaspi_tiyn.xlsx', 'rb'))
    return ConversationHandler.END

# Function to handle user's filter input
def received_information(update: Update, context: CallbackContext):
    user_data = context.user_data
    text = update.message.text
    category = user_data['choice']
    update.message.reply_text(f"Фильтр {category} на {text}. Парсинг начался. Как файл будет готов, отправлю сюда. Может занять некоторое время")
    scrape_data(category, text)  # Call scraping function with filtering
    update.message.reply_text('Парсинг закончился. Отправляю вам готовый файл')
    context.bot.send_document(chat_id=update.effective_chat.id, document=open('kaspi_tiyn.xlsx', 'rb'))
    user_data.clear()
    return ConversationHandler.END

# Function to end the conversation
def done(update: Update, context: CallbackContext):
    update.message.reply_text("Goodbye!")
    return ConversationHandler.END

def main():
    # Replace 'YOUR_TOKEN' with the token you got from BotFather
    updater = Updater("6738959845:AAG9mJxSbqTcc_6JfvA9D6d1Zo7cF45mR2k", use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Add conversation handler with states
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSING: [MessageHandler(Filters.regex('^(Бренд|Поставщик)$'), regular_choice)],
            TYPING_REPLY: [MessageHandler(Filters.text & ~(Filters.command | Filters.regex('^Done$')), received_information),
                           CommandHandler('skip', skip)],
        },
        fallbacks=[MessageHandler(Filters.regex('^Done$'), done)]
    )
    dp.add_handler(conv_handler)

    # Start the Bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()


# def scrape_data():
#     with open('output_qural_top125.csv', encoding='utf-8-sig') as f:
#         reader = list(csv.DictReader(f, delimiter=';'))
#         with open('kaspi.csv', 'w', newline='', encoding='utf-8') as f2:
#             writer = csv.DictWriter(
#                 f2,
#                 fieldnames=list(reader[0].keys()) + ['Продавец_1', 'Цена_1', 'Продавец_2', 'Цена_2', 'Продавец_3', 'Цена_3', 'Продавец_4', 'Цена_4', 'Продавец_5', 'Цена_5']
#             )
#             writer.writeheader()
#             for row in reader:
#                 print(f'scraping {row["Ссылки"]}')
#                 parse_offers(row, writer)
#
#     wb = Workbook()
#     ws = wb.active
#     with open('kaspi.csv', 'r', encoding='utf-8') as f:
#         for row in csv.reader(f):
#             ws.append(row)
#     wb.save('kaspi_tiyn.xlsx')
#
# # Define a command handler for scraping
# def scrape(update: Update, context: CallbackContext):
#     update.message.reply_text('Scraping data, please wait...')
#     scrape_data()
#     update.message.reply_text('Scraping completed. Sending file...')
#     context.bot.send_document(chat_id=update.effective_chat.id, document=open('kaspi_tiyn.xlsx', 'rb'))
#
# # Define the main function to set up the bot
# def main():
#     # Replace 'YOUR_TOKEN' with the token you got from BotFather
#     updater = Updater("6738959845:AAG9mJxSbqTcc_6JfvA9D6d1Zo7cF45mR2k", use_context=True)
#
#     # Get the dispatcher to register handlers
#     dp = updater.dispatcher
#
#     # Add command handler for scraping
#     dp.add_handler(CommandHandler("scrape", scrape))
#
#     # Start the Bot
#     updater.start_polling()
#     updater.idle()
#
# if __name__ == '__main__':
#     main()
