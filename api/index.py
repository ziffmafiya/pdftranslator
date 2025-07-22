import os
import deepl
import yandex.cloud.ai.translation.v2.translation_service_pb2 as yandex_ts_pb2
import yandex.cloud.ai.translation.v2.translation_service_pb2_grpc as yandex_ts_grpc
import yandexcloud
from flask import Flask, request, render_template, send_from_directory, flash, redirect, url_for
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

# --- App & Path Configuration ---
APP_ROOT = os.environ.get('VERCEL_BUILD_DIR', os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
TEMPLATE_DIR = os.path.join(APP_ROOT, 'templates')
app = Flask(__name__, template_folder=TEMPLATE_DIR)

UPLOAD_FOLDER = '/tmp/uploads'
DOWNLOAD_FOLDER = '/tmp/downloads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['DOWNLOAD_FOLDER'] = DOWNLOAD_FOLDER
app.config['SECRET_KEY'] = os.urandom(24)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)

# --- API Client Configuration ---
# DeepL
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
deepl_client = deepl.DeepLClient(DEEPL_API_KEY) if DEEPL_API_KEY else None

# Yandex
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")
yandex_sdk = yandexcloud.SDK(iam_token=YANDEX_API_KEY) if YANDEX_API_KEY else None
yandex_translator = yandex_sdk.client(yandex_ts_grpc.TranslationServiceStub) if yandex_sdk else None

# Supported languages by DeepL for translation
SUPPORTED_LANGUAGES = {
    "RU": "Russian",
    "UK": "Ukrainian"
}

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # --- File Handling ---
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if not file or not file.filename.endswith('.pdf'):
            flash('Please upload a valid PDF file')
            return redirect(request.url)

        filename = secure_filename(file.filename)
        source_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(source_path)

        # --- Form Data ---
        target_lang = request.form.get('language')
        service = request.form.get('service', 'deepl')

        if not target_lang:
            flash('Please select a language')
            return redirect(request.url)

        # --- Translation Logic ---
        try:
            output_filename = f"translated_{service}_{filename}"
            output_path = os.path.join(app.config['DOWNLOAD_FOLDER'], output_filename)

            if service == 'deepl':
                if not deepl_client:
                    raise ValueError("DeepL API key is not configured.")
                translate_pdf_deepl(source_path, output_path, target_lang)
            elif service == 'yandex':
                if not yandex_translator or not YANDEX_FOLDER_ID:
                    raise ValueError("Yandex API key or Folder ID is not configured.")
                translate_pdf_yandex(source_path, output_path, target_lang)
            else:
                raise ValueError("Invalid translation service selected.")

            return redirect(url_for('download_file', filename=output_filename))
        except Exception as e:
            flash(f'An error occurred: {e}')
            return redirect(request.url)

    return render_template('index.html', languages=SUPPORTED_LANGUAGES)

def translate_pdf_deepl(source_path, output_path, target_lang):
    """Translates a PDF document using the DeepL API."""
    deepl_client.translate_document_from_filepath(
        source_path,
        output_path,
        target_lang=target_lang,
    )
    print(f"DeepL translation complete. Saved to: {output_path}")

def translate_pdf_yandex(source_path, output_path, target_lang):
    """Translates a PDF document using the Yandex.Cloud Translation API."""
    with open(source_path, "rb") as f:
        file_content = f.read()

    request = yandex_ts_pb2.TranslateDocumentRequest(
        folder_id=YANDEX_FOLDER_ID,
        target_language_code=target_lang,
        document={
            "content": file_content
        }
    )
    
    result = yandex_translator.TranslateDocument(request)
    
    with open(output_path, "wb") as f:
        f.write(result.document.content)
    print(f"Yandex translation complete. Saved to: {output_path}")

@app.route('/downloads/<filename>')
def download_file(filename):
    return send_from_directory(app.config['DOWNLOAD_FOLDER'], filename, as_attachment=True)

# This part is not needed for Vercel deployment, but good for local testing
if __name__ == '__main__':
    app.run(debug=True)
