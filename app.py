import os
import deepl
from flask import Flask, request, render_template, send_from_directory, flash, redirect, url_for
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Vercel uses a /tmp directory for temporary file storage.
UPLOAD_FOLDER = '/tmp/uploads'
DOWNLOAD_FOLDER = '/tmp/downloads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['DOWNLOAD_FOLDER'] = DOWNLOAD_FOLDER
app.config['SECRET_KEY'] = os.urandom(24)

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)

DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
if not DEEPL_API_KEY:
    raise ValueError("No DEEPL_API_KEY set for Flask application")

deepl_client = deepl.DeepLClient(DEEPL_API_KEY)

# Supported languages by DeepL for translation
SUPPORTED_LANGUAGES = {
    "RU": "Russian",
    "UK": "Ukrainian"
}

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and file.filename.endswith('.pdf'):
            filename = secure_filename(file.filename)
            source_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(source_path)

            target_lang = request.form.get('language')
            if not target_lang:
                flash('Please select a language')
                return redirect(request.url)

            try:
                output_filename = f"translated_{filename}"
                output_path = os.path.join(app.config['DOWNLOAD_FOLDER'], output_filename)
                
                translate_pdf(source_path, output_path, target_lang)

                return redirect(url_for('download_file', filename=output_filename))
            except Exception as e:
                flash(f'An error occurred during translation: {e}')
                return redirect(request.url)

    return render_template('index.html', languages=SUPPORTED_LANGUAGES)

def translate_pdf(source_path, output_path, target_lang):
    """
    Переводит PDF-документ, используя официальную функцию DeepL.
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
    return send_from_directory(app.config['DOWNLOAD_FOLDER'], filename, as_attachment=True)

# This part is not needed for Vercel deployment, but good for local testing
if __name__ == '__main__':
    app.run(debug=True)
