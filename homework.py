import os
import time
import logging
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 5
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщение"""
    try:
        bot = bot
        message = message
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(f'Сообщение отправлено в чат '
                    f'{TELEGRAM_CHAT_ID}: {message}')
    except Exception as error:
        logger.error(f'Сообщение не отправлено ошибка:{error}')


def get_api_answer(current_timestamp):
    """Получает словарь с данными о домашней работе"""
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
    homework_statuses = requests.get(ENDPOINT, headers=headers, params=params)
    if homework_statuses.status_code != HTTPStatus.OK:
        logger.error(f'Ошибка {homework_statuses.status_code}!')
        raise Exception(f'Ошибка {homework_statuses.status_code}!')
    return homework_statuses.json()


def check_response(response):
    """Проверяет корректность полученных данных"""
    if isinstance(response, dict):
        return response['homeworks']


def parse_status(homework):
    """Извлекает статус домашней работы из словаря"""
    homework_name = homework[0]['homework_name']
    homework_status = homework[0]['status']
    if 'homework_name' not in homework[0]:
        logger.error('Работы с таким именем не обнаружено')
        raise KeyError('Работы с таким именем не обнаружено')
    if homework_status not in HOMEWORK_STATUSES:
        logger.error('Непредвиденный статус работы')
        raise KeyError('Непредвиденный статус работы')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет наличие всех токенов."""
    try:
        if all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
            return True
    except KeyError:
        logger.critical('Отсутствует одна из переменных окружения')


def main():
    """Основная логика работы бота."""

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = 0
    check_tokens()
    count_errors = 0

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if len(homework) == 0:
                logger.debug('Статус работы не изменился')
                time.sleep(RETRY_TIME)
                continue
            message = parse_status(homework)
            send_message(bot, message)
            current_timestamp = response.get('current_date')
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if count_errors == 0:
                send_message(bot, message)
            count_errors += 1
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
