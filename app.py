# app.py
#
# Этот файл содержит основную логику Flask-приложения для перевода PDF-документов
# с использованием DeepL, Google Translate и ApyHub API. Он предназначен для локального тестирования и разработки.
# Для развертывания на Vercel используется файл `api/index.py`, который имеет аналогичную логику.

import os
import deepl
import requests # Используется для взаимодействия с API ApyHub и LibreTranslate
from flask import Flask, request, render_template, send_from_directory, flash, redirect, url_for
from werkzeug.utils import secure_filename
import json # Используется для парсинга учетных данных JSON для Google Translate
from dotenv import load_dotenv # Для загрузки переменных окружения из файла .env
from google.cloud import translate_v3beta1 # Using v3beta1 for document translation features
import google.oauth2.service_account # Added for explicit credential loading
from google.cloud import storage # Added for Google Cloud Storage operations
# import fitz # PyMuPDF for LibreTranslate text extraction/reinsertion (commented out)

# Загрузка переменных окружения из файла .env
load_dotenv()

# Определение абсолютного пути к корневому каталогу проекта.
# Это важно для корректной работы как локально, так и при развертывании на Vercel.
APP_ROOT = os.environ.get('VERCEL_BUILD_DIR', os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
TEMPLATE_DIR = os.path.join(APP_ROOT, 'templates') # Путь к каталогу с шаблонами Jinja2

# Инициализация Flask-приложения
app = Flask(__name__, template_folder=TEMPLATE_DIR)

# Определение папок для загрузки и скачивания файлов.
# На Vercel используется каталог /tmp для временного хранения файлов.
UPLOAD_FOLDER = '/tmp/uploads'
DOWNLOAD_FOLDER = '/tmp/downloads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['DOWNLOAD_FOLDER'] = DOWNLOAD_FOLDER
app.config['SECRET_KEY'] = os.urandom(24) # Установка секретного ключа для безопасности сессий Flask

# Создание необходимых каталогов, если они еще не существуют
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)

# Инициализация клиента DeepL (условно).
# Клиент DeepL инициализируется только при наличии DEEPL_API_KEY в переменных окружения.
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
deepl_client = None
if DEEPL_API_KEY:
    deepl_client = deepl.DeepLClient(DEEPL_API_KEY)
    print("DeepL client initialized.")
else:
    print("DEEPL_API_KEY not set. DeepL translation will not be available.")

# Инициализация клиента Google Translate (условно).
# Клиент Google Translate инициализируется при наличии GOOGLE_CLOUD_PROJECT_ID
# и, опционально, GOOGLE_APPLICATION_CREDENTIALS_JSON для явной загрузки учетных данных.
google_credentials_json_content = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
google_translate_client = None
google_storage_client = None
GOOGLE_CLOUD_PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
GOOGLE_CLOUD_LOCATION = "global" # Местоположение для Google Cloud Translate API
GOOGLE_CLOUD_STORAGE_BUCKET = os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET")

if google_credentials_json_content and GOOGLE_CLOUD_PROJECT_ID:
    try:
        credentials_info = json.loads(google_credentials_json_content)
        credentials = google.oauth2.service_account.Credentials.from_service_account_info(credentials_info)
        google_translate_client = translate_v3beta1.TranslationServiceClient(credentials=credentials)
        google_storage_client = storage.Client(credentials=credentials, project=GOOGLE_CLOUD_PROJECT_ID)
        print("Google Translate and Storage clients initialized with explicit JSON credentials.")
    except json.JSONDecodeError as e:
        print(f"Error decoding GOOGLE_APPLICATION_CREDENTIALS_JSON: {e}. Google Translate will not be available.")
    except Exception as e:
        print(f"Error initializing Google Translate/Storage clients with JSON credentials: {e}. Google Translate will not be available.")
elif GOOGLE_CLOUD_PROJECT_ID:
    # Если JSON-учетные данные не предоставлены, используется Application Default Credentials (ADC).
    # Это работает локально при `gcloud auth application-default login`
    # или при установке GOOGLE_APPLICATION_CREDENTIALS в путь к файлу ключа сервисного аккаунта.
    google_translate_client = translate_v3beta1.TranslationServiceClient()
    google_storage_client = storage.Client(project=GOOGLE_CLOUD_PROJECT_ID)
    print("Google Translate and Storage clients initialized using Application Default Credentials (ADC).")
else:
    print("GOOGLE_CLOUD_PROJECT_ID or GOOGLE_APPLICATION_CREDENTIALS_JSON not set. Google Translate will not be available.")

if not GOOGLE_CLOUD_STORAGE_BUCKET:
    print("GOOGLE_CLOUD_STORAGE_BUCKET not set. Google Cloud Document Translation will not be fully functional.")

# Инициализация клиента ApyHub (условно).
# Клиент ApyHub инициализируется только при наличии APYHUB_API_KEY.
APYHUB_API_KEY = os.getenv("APYHUB_API_KEY")
APYHUB_TRANSLATE_DOC_URL = "https://api.apyhub.com/translate/file" # Обновленный URL API для перевода документов ApyHub
if not APYHUB_API_KEY:
    print("APYHUB_API_KEY not set. ApyHub translation will not be available.")

# # Инициализация LibreTranslate (с использованием requests) (закомментировано)
# # LIBRETRANSLATE_API_URL = os.getenv("LIBRETRANSLATE_API_URL")
# # if not LIBRETRANSLATE_API_URL:
# #     raise ValueError("No LIBRETRANSLATE_API_URL set for Flask application")

# Поддерживаемые языки для перевода.
# Обратите внимание, что разные API могут поддерживать разные наборы языков.
SUPPORTED_LANGUAGES = {
    "RU": "Russian",
    "UK": "Ukrainian"
}

@app.route('/', methods=['GET', 'POST'])
def index():
    """
    Обрабатывает запросы на главной странице.
    GET-запрос: отображает форму загрузки.
    POST-запрос: обрабатывает загрузку файла и запускает перевод.
    """
    if request.method == 'POST':
        # Проверка наличия файла в запросе
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # Проверка, был ли выбран файл
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        # Проверка типа файла (только PDF)
        if file and file.filename.endswith('.pdf'):
            filename = secure_filename(file.filename) # Очистка имени файла для безопасности
            source_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(source_path) # Сохранение загруженного файла

            target_lang = request.form.get('language') # Получение выбранного языка перевода
            if not target_lang:
                flash('Please select a language')
                return redirect(request.url)
            
            translation_engine = request.form.get('engine') # Получение выбранного движка перевода
            if not translation_engine:
                flash('Please select a translation engine.')
                return redirect(request.url)

            try:
                # Формирование имени выходного файла и пути
                output_filename = f"translated_{translation_engine}_{filename}"
                output_path = os.path.join(app.config['DOWNLOAD_FOLDER'], output_filename)
                
                # Вызов функции перевода PDF
                translate_pdf(source_path, output_path, target_lang, translation_engine)

                # Перенаправление на страницу скачивания переведенного файла
                return redirect(url_for('download_file', filename=output_filename))
            except Exception as e:
                # Обработка ошибок, возникших во время перевода
                flash(f'An error occurred during translation: {e}')
                return redirect(request.url)

    # Отображение шаблона index.html с доступными языками
    return render_template('index.html', languages=SUPPORTED_LANGUAGES)

def translate_pdf(source_path, output_path, target_lang, engine):
    """
    Переводит PDF-документ, используя выбранный API (DeepL, Google, ApyHub).
    
    Args:
        source_path (str): Путь к исходному PDF-файлу.
        output_path (str): Путь для сохранения переведенного PDF-файла.
        target_lang (str): Код целевого языка (например, "RU", "UK").
        engine (str): Выбранный движок перевода ("deepl", "google", "apyhub").
    
    Raises:
        ValueError: Если выбранный движок не настроен или недействителен.
        Exception: В случае ошибок API или других проблем с переводом.
    """
    if engine == 'deepl':
        # Проверка, настроен ли клиент DeepL
        if not deepl_client:
            raise ValueError("DeepL API key is not configured. Please set DEEPL_API_KEY in your .env file.")
        print(f"Using DeepL for translation to {target_lang}")
        deepl_client.translate_document_from_filepath(
            source_path,
            output_path,
            target_lang=target_lang,
        )
    elif engine == 'google':
        # Проверка, настроен ли клиент Google Translate
        if not google_translate_client or not GOOGLE_CLOUD_PROJECT_ID or not google_storage_client or not GOOGLE_CLOUD_STORAGE_BUCKET:
            raise ValueError("Google Translate is not fully configured. Please ensure GOOGLE_CLOUD_PROJECT_ID, GOOGLE_APPLICATION_CREDENTIALS_JSON (or ADC setup), and GOOGLE_CLOUD_STORAGE_BUCKET are set in your .env file.")
        print(f"Using Google Translate for translation to {target_lang}")

        # Google Cloud Document Translation requires Google Cloud Storage.
        # Upload the source file to GCS.
        source_blob_name = f"uploads/{os.path.basename(source_path)}"
        bucket = google_storage_client.bucket(GOOGLE_CLOUD_STORAGE_BUCKET)
        blob = bucket.blob(source_blob_name)
        blob.upload_from_filename(source_path)
        gcs_source_uri = f"gs://{GOOGLE_CLOUD_STORAGE_BUCKET}/{source_blob_name}"
        print(f"Uploaded {source_path} to {gcs_source_uri}")

        # Define the GCS output URI. Google will create a directory for the translated file.
        output_blob_prefix = f"translated/{os.path.basename(output_path).replace('.pdf', '')}/"
        gcs_output_uri = f"gs://{GOOGLE_CLOUD_STORAGE_BUCKET}/{output_blob_prefix}"
        print(f"Translation output will be saved to {gcs_output_uri}")

        input_configs = [
            {"gcs_source": {"input_uri": gcs_source_uri}}
        ]
        output_config = {"gcs_destination": {"output_uri_prefix": gcs_output_uri}}

        parent = f"projects/{GOOGLE_CLOUD_PROJECT_ID}/locations/{GOOGLE_CLOUD_LOCATION}"

        operation = google_translate_client.batch_translate_document(
            parent=parent,
            source_language_code="auto", # Automatically detect source language
            target_language_codes=[target_lang.lower()],
            input_configs=input_configs,
            output_config=output_config,
        )

        print("Waiting for Google Cloud Document Translation operation to complete...")
        response = operation.result(timeout=300) # Wait for the operation to complete, with a timeout
        print("Google Cloud Document Translation operation completed.")

        # The translated file will be in a subdirectory created by Google.
        # We need to find the actual translated file in GCS and download it.
        translated_blobs = list(bucket.list_blobs(prefix=output_blob_prefix))
        translated_pdf_blob = None
        for b in translated_blobs:
            if b.name.endswith('.pdf'):
                translated_pdf_blob = b
                break

        if translated_pdf_blob:
            translated_pdf_blob.download_to_filename(output_path)
            print(f"Downloaded translated file from GCS: {translated_pdf_blob.name} to {output_path}")
        else:
            raise Exception("Translated PDF file not found in Google Cloud Storage output.")

        # Clean up: Optionally delete the uploaded source file and translated files from GCS
        # blob.delete()
        # if translated_pdf_blob:
        #     translated_pdf_blob.delete()
        # print("Cleaned up temporary files in GCS.")
        
    elif engine == 'apyhub':
        # Проверка, настроен ли клиент ApyHub
        if not APYHUB_API_KEY:
            raise ValueError("ApyHub API key is not configured. Please set APYHUB_API_KEY in your .env file.")
        print(f"Using ApyHub for translation to {target_lang}")
        # Логика для вызова API перевода документов ApyHub
        headers = {
            "apy-token": APYHUB_API_KEY,
            # 'content-type': 'multipart/form-data', # requests добавит границу, если этот заголовок установлен при передаче files=
        }
        
        # Параметры, если они нужны (например, transliteration)
        params = {
            'transliteration': 'false', # Установите 'true', если требуется транслитерация
        }

        files = {
            'file': open(source_path, 'rb'),
            'language': (None, 'ua' if target_lang == 'UK' else target_lang.lower()), # ApyHub использует 'ua' для украинского, 'ru' для русского
        }
        
        try:
            response = requests.post(APYHUB_TRANSLATE_DOC_URL, params=params, headers=headers, files=files)
            response.raise_for_status() # Вызывает исключение для HTTP-ошибок (4xx или 5xx)
            
            # Сохранение переведенного содержимого в выходной файл
            with open(output_path, 'wb') as f:
                f.write(response.content)
            print(f"ApyHub Translation completed. Saved file: {output_path}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"ApyHub API error: {e}")
        finally:
            files["file"][0].close() # Гарантированное закрытие файла
            
#     elif engine == 'libretranslate':
#         print(f"Using LibreTranslate for translation to {target_lang}")
#         # LibreTranslate в основном работает с текстом.
#         # Для сохранения макета требуется извлечение/повторная вставка текста с помощью PyMuPDF.
#         # Это сложная задача, которая может не идеально сохранять макет.
        
#         doc = fitz.open(source_path)
#         new_doc = fitz.open()

#         for page_num in range(len(doc)):
#             page = doc.load_page(page_num)
#             new_page = new_doc.new_page(width=page.rect.width, height=page.rect.height)
            
#             text_spans = []
#             texts_to_translate = []
#             blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]
#             for block in blocks:
#                 if block['type'] == 0:
#                     for line in block['lines']:
#                         for span in line['spans']:
#                             if span['text'].strip():
#                                 text_spans.append(span)
#                                 texts_to_translate.append(span['text'])

#             if not texts_to_translate:
#                 new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
#                 continue

#             # Перевод текстов с использованием LibreTranslate
#             libre_headers = {'Content-Type': 'application/json'}
#             libre_data = {
#                 "q": texts_to_translate,
#                 "source": "auto", # LibreTranslate может автоматически определять язык
#                 "target": target_lang.lower()
#             }
            
#             try:
#                 libre_response = requests.post(f"{LIBRETRANSLATE_API_URL}/translate", json=libre_data, headers=libre_headers)
#                 libre_response.raise_for_status()
#                 translated_texts = [r['translatedText'] for r in libre_response.json()]
#             except requests.exceptions.RequestException as e:
#                 raise Exception(f"LibreTranslate API error: {e}")

#             if len(translated_texts) != len(text_spans):
#                 raise Exception("LibreTranslate returned a different number of items than expected.")

#             # Реконструкция страницы с переведенным текстом
#             # Повторное введение обработки шрифтов для LibreTranslate
#             font_path = os.path.join(APP_ROOT, "DejaVuSans.ttf") # Предполагается, что DejaVuSans.ttf находится в корневом каталоге проекта
#             font_name = "DejaVu"
#             if not os.path.exists(font_path):
#                 raise FileNotFoundError("Font file 'DejaVuSans.ttf' not found for LibreTranslate. Please download it and place it in the project directory.")
            
#             new_page.insert_font(fontname=font_name, fontfile=font_path)

#             translated_text_index = 0
#             for block in blocks:
#                 if block['type'] == 0:
#                     original_spans_in_block = []
#                     for line in block['lines']:
#                         for span in line['spans']:
#                             if span['text'].strip():
#                                 original_spans_in_block.append(span)
                    
#                     if not original_spans_in_block:
#                         continue

#                     translated_texts_for_block = []
#                     for _ in original_spans_in_block:
#                         if translated_text_index < len(translated_texts):
#                             translated_texts_for_block.append(translated_texts[translated_text_index])
#                             translated_text_index += 1
                    
#                     full_translated_text = " ".join(translated_texts_for_block)

#                     first_span = original_spans_in_block[0]
#                     srgb = first_span['color']
#                     r = ((srgb >> 16) & 0xff) / 255.0
#                     g = ((srgb >> 8) & 0xff) / 255.0
#                     b = (srgb & 0xff) / 255.0
#                     color = (r, g, b)
#                     font_size = first_span['size']

#                     new_page.insert_textbox(block['bbox'], full_translated_text, fontsize=font_size, fontname=font_name, color=color, align=fitz.TEXT_ALIGN_LEFT)

#         new_doc.save(output_path)
#         new_doc.close()
#         doc.close()
#         print(f"LibreTranslate Translation completed. Saved file: {output_path}")
    else:
        raise ValueError("Invalid translation engine selected.")
    
    print(f"Перевод завершён. Сохранён файл: {output_path}")

@app.route('/downloads/<filename>')
def download_file(filename):
    """
    Предоставляет переведенные файлы для скачивания.
    """
    return send_from_directory(app.config['DOWNLOAD_FOLDER'], filename, as_attachment=True)

# Эта часть не нужна для развертывания на Vercel, но полезна для локального тестирования.
if __name__ == '__main__':
    app.run(debug=True)
