from flask import Flask, request, jsonify, render_template, send_file
from werkzeug.utils import secure_filename
import os
from PyPDF2 import PdfReader
from gtts import gTTS
from fpdf import FPDF
import nltk

# Configure NLTK path
NLTK_DIR = '/opt/render/nltk_data'
os.makedirs(NLTK_DIR, exist_ok=True)
nltk.data.path.append(NLTK_DIR)

# Download required resources if not already present
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', download_dir=NLTK_DIR)

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', download_dir=NLTK_DIR)

import re
import heapq
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

simple_synonyms = {
    "complicated": "hard",
    "difficult": "hard",
    "complex": "simple",
    "elaborate": "explain",
    "demonstrate": "show",
    "understanding": "idea",
    "utilize": "use",
    "assist": "help",
    "facilitate": "help",
    "objective": "goal",
    "significant": "important",
    "process": "steps",
    "concept": "idea",
}

def simplify_text(text):
    sentences = sent_tokenize(text, language='english')
    simplified_sentences = []
    for sentence in sentences:
        words = word_tokenize(sentence)
        simplified_words = [simple_synonyms.get(word.lower(), word) for word in words]
        chunk_size = 8
        chunks = [' '.join(simplified_words[i:i+chunk_size]) for i in range(0, len(simplified_words), chunk_size)]
        simplified_sentences.append('\n'.join(chunks))
    return '\n\n'.join(simplified_sentences)

def summarize_text(text, max_sentences=3):
    stop_words = set(stopwords.words("english"))
    word_freq = {}
    sentences = sent_tokenize(text, language='english')

    for sentence in sentences:
        for word in word_tokenize(sentence.lower()):
            if word.isalpha() and word not in stop_words:
                word_freq[word] = word_freq.get(word, 0) + 1

    if not word_freq:
        return "Summary not possible due to insufficient content."

    sentence_scores = {}
    for sentence in sentences:
        for word in word_tokenize(sentence.lower()):
            if word in word_freq:
                sentence_scores[sentence] = sentence_scores.get(sentence, 0) + word_freq[word]

    best_sentences = heapq.nlargest(max_sentences, sentence_scores, key=sentence_scores.get)
    return ' '.join(best_sentences)

def extract_text_from_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/simplify', methods=['POST'])
def simplify():
    data = request.json
    text = data.get('text', '')
    if not text:
        return jsonify({'error': 'No text provided'}), 400
    simplified_text = simplify_text(text)
    return jsonify({'simplified_text': simplified_text})

@app.route('/summarize', methods=['POST'])
def summarize():
    data = request.json
    text = data.get('text', '')
    if not text:
        return jsonify({'error': 'No text provided'}), 400
    summary = summarize_text(text)
    return jsonify({'summary': summary})

@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    if 'pdf' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['pdf']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        extracted_text = extract_text_from_pdf(filepath)
        simplified_text = simplify_text(extracted_text)

        with open(os.path.join(PROCESSED_FOLDER, 'simplified.txt'), 'w', encoding='utf-8') as f:
            f.write(simplified_text)

        return jsonify({'message': 'PDF processed successfully', 'simplified_text': simplified_text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/save_simplified', methods=['POST'])
def save_simplified():
    data = request.json
    text = data.get('text', '')
    filename = secure_filename(data.get('filename', 'simplified_output.txt'))
    if not text:
        return jsonify({'error': 'No text provided'}), 400
    filepath = os.path.join(PROCESSED_FOLDER, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)
    return jsonify({'message': 'Simplified text saved successfully'})

@app.route('/download_pdf')
def download_pdf():
    txt_path = os.path.join(PROCESSED_FOLDER, 'simplified.txt')
    if not os.path.exists(txt_path):
        return jsonify({'error': 'No simplified text available'}), 404
    pdf_path = os.path.join(PROCESSED_FOLDER, 'simplified.pdf')
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', size=12)
    with open(txt_path, 'r', encoding='utf-8') as f:
        for line in f:
            pdf.multi_cell(0, 10, line)
    pdf.output(pdf_path)
    return send_file(pdf_path, as_attachment=True)

@app.route('/download_txt')
def download_txt():
    txt_path = os.path.join(PROCESSED_FOLDER, 'simplified.txt')
    if not os.path.exists(txt_path):
        return jsonify({'error': 'No simplified text available'}), 404
    return send_file(txt_path, as_attachment=True)

@app.route('/text_to_speech', methods=['POST'])
def text_to_speech():
    data = request.json
    text = data.get('text', '')
    if not text:
        return jsonify({'error': 'No text provided'}), 400
    audio_path = os.path.join(PROCESSED_FOLDER, 'speech.mp3')
    tts = gTTS(text)
    tts.save(audio_path)
    return send_file(audio_path, mimetype='audio/mpeg')

@app.route('/pronunciation_feedback', methods=['POST'])
def pronunciation_feedback():
    data = request.json
    user_audio = data.get('audio')
    correct_text = data.get('text')
    if not user_audio or not correct_text:
        return jsonify({'error': 'Audio or text not provided'}), 400
    feedback = "Your pronunciation is good!"  # Placeholder
    return jsonify({'feedback': feedback})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
