import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from telegram import TelegramError

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)


def send_message(bot, message):
    """Отправляет сообщение."""
    try:
        message = message
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(f'Сообщение отправлено в чат '
                    f'{TELEGRAM_CHAT_ID}: {message}')
    except TelegramError as error:
        logger.error(f'Сообщение с текстом: '
                     f'{message} не отправлено ошибка:{error}', exc_info=True)


def send_error_message(exception, error_description):
    """Отправка сообщения об ошибке в Телеграм и в лог."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    message = f'{exception} {error_description}'
    logger.error(message)
    logger.info('Бот отправляет в Телеграм сообщение '
                'об ошибке в своей работе.')
    send_message(bot, message)


def get_api_answer(current_timestamp):
    """Получает словарь с данными о домашней работе."""
    homework_statuses = {}
    try:
        params = {'from_date': current_timestamp}
        headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
        response = requests.get(ENDPOINT, headers=headers, params=params)
        if response.status_code == HTTPStatus.OK:
            homework_statuses = response
        else:
            message = (f'Ошибка {response.status_code} '
                       f'при попытке доступа к API')
            send_error_message({response.status_code}, message)
    except requests.ConnectionError as e:
        message = 'Ошибка соединения при попытке доступа к API.'
        send_error_message(e, message)
    except requests.Timeout as e:
        message = 'Таймаут ошибка при попытке доступа к API.'
        send_error_message(e, message)
    except requests.RequestException as e:
        message = 'Ошибка отправки запроса при попытке доступа к API.'
        send_error_message(e, message)
    return homework_statuses.json()


def check_response(response):
    """Проверяет корректность ответа API."""
    logger.info('Начата проверка ответа от API')
    if not isinstance(response, dict):
        message = 'Ответ от API не является словарём'
        send_error_message(TypeError, message)
        raise TypeError()
    homework = response.get('homeworks')
    if homework is None:
        message = 'В ответе от API отсутствует ключ homeworks'
        send_error_message(KeyError, message)
        raise KeyError()
    if type(homework) is not list:
        message = 'По ключу homeworks находится не список'
        send_error_message(TypeError, message)
        raise TypeError()
    if response.get('current_date') is None:
        message = 'В ответе от API отсутствует ключ current_date'
        send_error_message(KeyError, message)
        raise KeyError()
    if type(response.get('current_date')) is not int:
        message = 'По ключу current_date находится не число'
        send_error_message(TypeError, message)
        raise TypeError()
    return homework


def parse_status(homework):
    """Извлекает статус домашней работы из словаря."""
    if homework['homework_name'] is None:
        message = 'В словаре отсутствует ключ homework_name'
        send_error_message(KeyError, message)
        raise KeyError()
    homework_name = homework['homework_name']
    if homework['status'] is None:
        message = 'В словаре отсутствует ключ homework_name'
        send_error_message(KeyError, message)
        raise KeyError()
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        message = 'Непредвиденный статус работы'
        send_error_message(ValueError, message)
        raise ValueError()
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет наличие всех токенов."""
    if all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        return True


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    if check_tokens() is not True:
        message = 'Отсутствует одна из переменных окружения'
        logger.critical(message)
        send_message(bot, message)
        sys.exit(1)

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if len(homework) == 0:
                logger.debug('Статус работы не изменился')
                time.sleep(RETRY_TIME)
                continue
            message = parse_status(homework[0])
            send_message(bot, message)
            current_timestamp = response.get('current_date')
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - функция %(funcName)s - строка %(lineno)d '
        '- %(name)s - %(levelname)s - %(message)s'
    )
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    main()
