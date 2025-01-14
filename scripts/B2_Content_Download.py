import boto3
from botocore.exceptions import BotoCoreError, ClientError
import json
from datetime import datetime
import os
import requests
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Конфигурация через переменные окружения
ENDPOINT = os.getenv("S3_ENDPOINT")
BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
KEY_ID = os.getenv("S3_KEY_ID")
APPLICATION_KEY = os.getenv("S3_APPLICATION_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

DIRECTORY = "a1/data/downloaded"
LOG_FILE = "a1/logs/operation_log.txt"
CONFIG_FILE = "a1/config/config_public.json"
FOLDERS = ["444/", "555/", "666/"]

# Логирование
def log_message(message):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    print(message)  # Дублируем лог в терминал
    with open(LOG_FILE, "a") as log:
        log.write(f"[{datetime.now()}] {message}\n")

# Функция для отправки одного файла
def send_file_to_telegram(file_path):
    """
    Отправляет файл в Telegram-канал.
    """
    log_message(f"Попытка отправки файла: {file_path}")
    try:
        # Проверка размера файла
        if os.path.getsize(file_path) > 50 * 1024 * 1024:
            log_message(f"Файл {file_path} превышает лимит размера Telegram (50 МБ).")
            return

        with open(file_path, "rb") as file:
            response = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument",
                data={"chat_id": CHAT_ID},
                files={"document": file}
            )
        log_message(f"Ответ Telegram API: {response.json()}")
        if response.status_code == 200:
            log_message(f"Файл {file_path} успешно отправлен в Telegram.")
        else:
            log_message(f"Ошибка при отправке файла {file_path}: {response.text}")
    except Exception as e:
        log_message(f"Исключение при отправке файла {file_path}: {e}")

# Функция для отправки всех файлов из директории
def send_downloaded_files_to_telegram(directory):
    """
    Отправляет все файлы из указанной директории в Telegram.
    """
    for file_name in os.listdir(directory):
        file_path = os.path.join(directory, file_name)
        send_file_to_telegram(file_path)

# Создание клиента S3
def create_s3_client():
    try:
        return boto3.client(
            's3',
            endpoint_url=ENDPOINT,
            aws_access_key_id=KEY_ID,
            aws_secret_access_key=APPLICATION_KEY
        )
    except Exception as e:
        log_message(f"Ошибка создания клиента S3: {e}")
        raise

# Проверка наличия группы файлов
def validate_group(files):
    required_extensions = {"json", "png", "mp4"}
    grouped_files = {}

    for file in files:
        name, ext = os.path.splitext(file["Key"])
        ext = ext.lstrip(".").lower()
        if ext in required_extensions:
            grouped_files.setdefault(name, set()).add(ext)

    for group, extensions in grouped_files.items():
        if extensions == required_extensions:
            return group

    return None

# Скачивание файлов группы
def download_files(s3_client, group_name):
    for ext in [".json", ".png", ".mp4"]:
        file_key = f"{group_name}{ext}"
        local_path = os.path.join(DIRECTORY, os.path.basename(file_key))
        try:
            s3_client.download_file(BUCKET_NAME, file_key, local_path)
            log_message(f"Скачан файл: {file_key}")
        except (BotoCoreError, ClientError) as e:
            log_message(f"Ошибка при скачивании {file_key}: {e}")
            return False
    return True

# Обновление конфигурационного файла
def update_config(folder):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    config = {"publish": folder, "empty": []}
    with open(CONFIG_FILE, "w") as config_file:
        json.dump(config, config_file, indent=4)
    log_message(f"Обновлен config_public.json: {config}")

# Проверка Telegram API
def test_telegram():
    response = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": "Тестовое сообщение из скрипта"}
    )
    log_message(f"Тестовый ответ Telegram API: {response.json()}")

# Основной процесс
def main():
    if not os.path.exists(DIRECTORY):
        os.makedirs(DIRECTORY)

    try:
        s3_client = create_s3_client()
    except Exception:
        log_message("Не удалось создать клиент S3.")
        return

    for folder in FOLDERS:
        try:
            response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=folder)

            if 'Contents' not in response:
                log_message(f"Нет файлов в папке: {folder}")
                continue

            group_name = validate_group(response['Contents'])
            if group_name:
                log_message(f"Найдена группа в папке {folder}: {group_name}")
                if download_files(s3_client, group_name):
                    send_downloaded_files_to_telegram(DIRECTORY)
                    update_config(folder)
                    return
            else:
                log_message(f"Группа в папке {folder} не найдена.")

        except (BotoCoreError, ClientError) as e:
            log_message(f"Ошибка доступа к папке {folder}: {e}")

    log_message("Во всех папках группы не найдены.")

if __name__ == "__main__":
    main()
    test_telegram()
