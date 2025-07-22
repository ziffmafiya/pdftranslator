import os
import deepl
import requests # For ApyHub and LibreTranslate
from flask import Flask, request, render_template, send_from_directory, flash, redirect, url_for
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from google.cloud import translate_v3beta1 as translate # Using v3beta1 for document translation features
# import fitz # PyMuPDF for LibreTranslate text extraction/reinsertion (commented out)

load_dotenv()

# Define the absolute path to the project's root directory
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

# Initialize DeepL client
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
if not DEEPL_API_KEY:
    raise ValueError("No DEEPL_API_KEY set for Flask application")
deepl_client = deepl.DeepLClient(DEEPL_API_KEY)

# Initialize Google Translate client
google_translate_client = translate.TranslationServiceClient()
GOOGLE_CLOUD_PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
if not GOOGLE_CLOUD_PROJECT_ID:
    raise ValueError("No GOOGLE_CLOUD_PROJECT_ID set for Flask application")
GOOGLE_CLOUD_LOCATION = "global"

# Initialize ApyHub client (using requests)
APYHUB_API_KEY = os.getenv("APYHUB_API_KEY")
if not APYHUB_API_KEY:
    raise ValueError("No APYHUB_API_KEY set for Flask application")
APYHUB_TRANSLATE_DOC_URL = "https://api.apyhub.com/api/v1/convert/document/translate/url" # Assuming URL-based for simplicity

# # Initialize LibreTranslate (using requests) (commented out)
# LIBRETRANSLATE_API_URL = os.getenv("LIBRETRANSLATE_API_URL")
# if not LIBRETRANSLATE_API_URL:
#     raise ValueError("No LIBRETRANSLATE_API_URL set for Flask application")

# Supported languages (DeepL, Google, ApyHub might have different sets)
# For simplicity, we'll keep the current limited set for now.
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
            
            translation_engine = request.form.get('engine')
            if not translation_engine:
                flash('Please select a translation engine.')
                return redirect(request.url)

            try:
                output_filename = f"translated_{translation_engine}_{filename}"
                output_path = os.path.join(app.config['DOWNLOAD_FOLDER'], output_filename)
                
                translate_pdf(source_path, output_path, target_lang, translation_engine)

                return redirect(url_for('download_file', filename=output_filename))
            except Exception as e:
                flash(f'An error occurred during translation: {e}')
                return redirect(request.url)

    return render_template('index.html', languages=SUPPORTED_LANGUAGES)

def translate_pdf(source_path, output_path, target_lang, engine):
    """
    Переводит PDF-документ, используя выбранный API (DeepL, Google, ApyHub, LibreTranslate).
    """
    if engine == 'deepl':
        print(f"Using DeepL for translation to {target_lang}")
        deepl_client.translate_document_from_filepath(
            source_path,
            output_path,
            target_lang=target_lang,
        )
    elif engine == 'google':
        print(f"Using Google Translate for translation to {target_lang}")
        raise NotImplementedError("Google Cloud Document Translation is not yet implemented due to its complexity. It requires Google Cloud Storage setup.")
        
    elif engine == 'apyhub':
        print(f"Using ApyHub for translation to {target_lang}")
        # ApyHub Document Translation API
        headers = {
            "apy-token": APYHUB_API_KEY
        }
        files = {
            "file": open(source_path, 'rb')
        }
        data = {
            "output": "pdf",
            "language": target_lang.lower() # ApyHub might use lowercase codes
        }
        
        try:
            response = requests.post(APYHUB_TRANSLATE_DOC_URL, headers=headers, files=files, data=data)
            response.raise_for_status() # Raise an exception for HTTP errors
            
            with open(output_path, 'wb') as f:
                f.write(response.content)
            print(f"ApyHub Translation completed. Saved file: {output_path}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"ApyHub API error: {e}")
        finally:
            files["file"].close() # Ensure file is closed
            
#     elif engine == 'libretranslate':
#         print(f"Using LibreTranslate for translation to {target_lang}")
#         # LibreTranslate is primarily text-based.
#         # To preserve layout, we need to re-introduce PyMuPDF text extraction/reinsertion.
#         # This is complex and might not perfectly preserve layout.
        
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

#             # Translate texts using LibreTranslate
#             libre_headers = {'Content-Type': 'application/json'}
#             libre_data = {
#                 "q": texts_to_translate,
#                 "source": "auto", # LibreTranslate can auto-detect
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

#             # Reconstruct the page with translated text
#             # Re-introducing font handling for LibreTranslate
#             font_path = os.path.join(APP_ROOT, "DejaVuSans.ttf") # Assuming DejaVuSans.ttf is in root
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
    return send_from_directory(app.config['DOWNLOAD_FOLDER'], filename, as_attachment=True)

# This part is not needed for Vercel deployment, but good for local testing
if __name__ == '__main__':
    app.run(debug=True)
