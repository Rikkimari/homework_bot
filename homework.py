import logging
import os
import sys
import time
from http import HTTPStatus
from json import JSONDecodeError

import requests
import telegram
from dotenv import load_dotenv
from requests import Response
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
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Сообщение успешно отправлено')
    except TelegramError as error:
        logger.error('Сообщение с текстом: '
                     f'{message} не отправлено ошибка:{error}', exc_info=True)


def send_error_message(exception, error_description):
    """Отправка сообщения об ошибке в Телеграм и в лог."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    message = f'{exception} {error_description}'
    logger.error(message)
    send_message(bot, message)


def get_api_answer(current_timestamp):
    """Получает словарь с данными о домашней работе."""
    params = {'from_date': current_timestamp}
    headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
    response_params = {'ENDPOINT': ENDPOINT,
                       'headers': headers,
                       'params': params}
    try:
        response = requests.get(url=response_params.get('ENDPOINT'),
                                headers=response_params.get('headers'),
                                params=response_params.get('params')
                                )
        if response.status_code != HTTPStatus.OK:
            error_message = (f'Ошибка {response.status_code} '
                             'при попытке запроса к API с параметрами'
                             f'{response_params}')
            logger.error(error_message)
            Response.raise_for_status(response)
        return response.json()

    except JSONDecodeError:
        logger.error(f'Запрос с параметрами {response_params} '
                     'вернул не валидный json', exc_info=True)
        raise


def check_response(response):
    """Проверяет корректность ответа API."""
    logger.info('Начата проверка ответа от API')
    if not isinstance(response, dict):
        message = 'Ответ от API не является словарём'
        logger.error(message)
        raise TypeError(message)
    homework = response.get('homeworks')
    if homework is None:
        message = 'В ответе от API отсутствует ключ homeworks'
        logger.error(message)
        raise KeyError(message)
    if type(homework) is not list:
        message = 'По ключу homeworks находится не список'
        logger.error(message)
        raise TypeError(message)
    if response.get('current_date') is None:
        message = 'В ответе от API отсутствует ключ current_date'
        logger.error(message)
        raise KeyError(message)
    if type(response.get('current_date')) is not int:
        message = 'По ключу current_date находится не число'
        logger.error(message)
        raise TypeError(message)
    return homework


def parse_status(homework):
    """Извлекает статус домашней работы из словаря."""
    if homework.get('homework_name') is None:
        message = 'В словаре отсутствует ключ homework_name'
        logger.error(message)
        raise KeyError(message)
    homework_name = homework['homework_name']
    if homework.get('status') is None:
        message = 'В словаре отсутствует ключ homework_name'
        logger.error(message)
        raise KeyError(message)
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        message = 'Непредвиденный статус работы'
        logger.error(message)
        raise ValueError(message)
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет наличие всех токенов."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    if not check_tokens():
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
                continue
            message = parse_status(homework[0])
            send_message(bot, message)
            current_timestamp = response.get('current_date')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        finally:
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
