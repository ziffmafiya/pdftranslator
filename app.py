# app.py
#
# Этот файл содержит основную логику Flask-приложения для перевода PDF-документов
# с использованием DeepL API. Он предназначен для локального тестирования и разработки.
# Для развертывания на Vercel используется файл `api/index.py`.

import os
import deepl
from flask import Flask, request, render_template, send_from_directory, flash, redirect, url_for
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Загрузка переменных окружения из файла .env
load_dotenv()

# Инициализация Flask-приложения
app = Flask(__name__)

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

# Получение ключа DeepL API из переменных окружения
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
# Проверка наличия ключа DeepL API. Если ключ отсутствует, будет вызвана ошибка.
if not DEEPL_API_KEY:
    raise ValueError("No DEEPL_API_KEY set for Flask application")

# Инициализация клиента DeepL
deepl_client = deepl.DeepLClient(DEEPL_API_KEY)

# Поддерживаемые языки для перевода DeepL
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

            try:
                # Формирование имени выходного файла и пути
                output_filename = f"translated_{filename}"
                output_path = os.path.join(app.config['DOWNLOAD_FOLDER'], output_filename)
                
                # Вызов функции перевода PDF
                translate_pdf(source_path, output_path, target_lang)

                # Перенаправление на страницу скачивания переведенного файла
                return redirect(url_for('download_file', filename=output_filename))
            except Exception as e:
                # Обработка ошибок, возникших во время перевода
                flash(f'An error occurred during translation: {e}')
                return redirect(request.url)

    # Отображение шаблона index.html с доступными языками
    return render_template('index.html', languages=SUPPORTED_LANGUAGES)

def translate_pdf(source_path, output_path, target_lang):
    """
    Переводит PDF-документ, используя официальную функцию DeepL.
    
    Args:
        source_path (str): Путь к исходному PDF-файлу.
        output_path (str): Путь для сохранения переведенного PDF-файла.
        target_lang (str): Код целевого языка (например, "RU", "UK").
    """
    try:
        deepl_client.translate_document_from_filepath(
            source_path,
            output_path,
            target_lang=target_lang,
        )
        print(f"Перевод завершён. Сохранён файл: {output_path}")
    except deepl.DocumentTranslationException as error:
        print(f"DocumentTranslationException: {error}")
        raise error
    except deepl.DeepLException as error:
        print(f"DeepLException: {error}")
        raise error

@app.route('/downloads/<filename>')
def download_file(filename):
    """
    Предоставляет переведенные файлы для скачивания.
    """
    return send_from_directory(app.config['DOWNLOAD_FOLDER'], filename, as_attachment=True)

# Эта часть не нужна для развертывания на Vercel, но полезна для локального тестирования.
if __name__ == '__main__':
    app.run(debug=True)
