import logging
import os
import sys
import time
from http import HTTPStatus
from json import JSONDecodeError

import requests
import telegram
from dotenv import load_dotenv
from requests import RequestException, Response
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
    except TelegramError as error:
        raise TelegramError('Сообщение с текстом: '
                            f'{message} не отправлено ошибка:{error}')
    else:
        logger.info('Сообщение успешно отправлено')


def get_api_answer(current_timestamp):
    """Получает словарь с данными о домашней работе."""
    response_params = {'ENDPOINT': ENDPOINT,
                       'headers': {'Authorization':
                                   f'OAuth {PRACTICUM_TOKEN}'},
                       'params': {'from_date': current_timestamp}}
    try:
        response = requests.get(**{'url': response_params.get('ENDPOINT'),
                                   'headers': response_params.get('headers'),
                                   'params': response_params.get('params')})
        if response.status_code != HTTPStatus.OK:
            Response.raise_for_status(response)

    except RequestException:
        raise RequestException((f'Ошибка {response.status_code} '
                                'при попытке запроса к API с параметрами'
                                f' {response_params}'))
    try:
        return response.json()
    except JSONDecodeError:
        raise


def check_response(response):
    """Проверяет корректность ответа API."""
    logger.info('Начата проверка ответа от API')
    if not isinstance(response, dict):
        raise TypeError('Ответ от API не является словарём')
    homeworks = response.get('homeworks')
    if homeworks is None:
        raise KeyError('В ответе от API отсутствует ключ homeworks')
    if type(homeworks) is not list:
        raise TypeError('По ключу homeworks находится не список')
    if response.get('current_date') is None:
        logger.error('В ответе от API отсутствует ключ current_date')
    if not isinstance((response.get('current_date')), int):
        raise TypeError('По ключу current_date находится не число')
    return homeworks


def parse_status(homework):
    """Извлекает статус домашней работы из словаря."""
    homework_name = homework.get('homework_name')
    if homework_name is None:
        raise KeyError('В словаре отсутствует ключ homework_name')
    homework_status = homework.get('status')
    if homework_status is None:
        raise KeyError('В словаре отсутствует ключ homework_name')
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError('Непредвиденный статус домашней работы')
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
            logger.error(message, exc_info=True)
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
