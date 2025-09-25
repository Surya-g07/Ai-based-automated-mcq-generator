import os
import uuid
import pdfplumber
import docx
from flask import Flask, render_template, request, session, redirect, url_for
from werkzeug.utils import secure_filename
import spacy
import random


nlp = spacy.load("en_core_web_sm")

app = Flask(__name__)
app.secret_key = 'super_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'txt', 'docx'}

session_storage = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def extract_text_from_file(file_path):
    ext = file_path.rsplit('.', 1)[1].lower()
    if ext == 'pdf':
        with pdfplumber.open(file_path) as pdf:
            return ''.join([page.extract_text() or '' for page in pdf.pages])
    elif ext == 'docx':
        doc = docx.Document(file_path)
        return ' '.join([para.text for para in doc.paragraphs])
    elif ext == 'txt':
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    return None

def generate_mcqs_local(text, num_questions):
    doc = nlp(text)
    sentences = list(doc.sents)
    mcqs = []

    
    for sent in sentences:
        if len(mcqs) >= num_questions:
            break

        tokens = [token for token in sent if token.pos_ in ('NOUN', 'PROPN')]
        if not tokens:
            continue

        answer_token = random.choice(tokens)
        answer = answer_token.text
        question_text = sent.text.replace(answer, "_____")

        
        all_nouns = [token.text for token in doc if token.pos_ in ('NOUN', 'PROPN')]
        options = set([answer])
        while len(options) < 4:
            options.add(random.choice(all_nouns))
        options = list(options)
        random.shuffle(options)

        correct_option_index = options.index(answer)
        option_labels = ['A', 'B', 'C', 'D']
        options_labeled = list(zip(option_labels, options))

        mcqs.append({
            "question": question_text,
            "options": options_labeled,
            "correct": option_labels[correct_option_index]
        })

    return mcqs

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        role = request.form.get('role')

        if not username or not role:
            return "Username and role required.", 400

        session['username'] = username
        session['role'] = role

        if role == 'teacher':
            return redirect(url_for('index'))
        elif role == 'student':
            return redirect(url_for('student'))
        else:
            return "Invalid role", 400
    return render_template('login.html')

@app.route('/index')
def index():
    if session.get('role') != 'teacher':
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/teacher', methods=['POST'])
def teacher_generate():
    if session.get('role') != 'teacher':
        return redirect(url_for('login'))

    file = request.files['file']
    if not file or not allowed_file(file.filename):
        return "Invalid file"

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    file.save(filepath)

    text = extract_text_from_file(filepath)
    if not text:
        return "Failed to extract text from file."

    num_questions = int(request.form['num_questions'])
    mcqs = generate_mcqs_local(text, num_questions)

    session_key = str(uuid.uuid4())[:8]
    session_storage[session_key] = {
        "mcqs": mcqs,
        "timer": int(request.form.get('timer', 0))
    }

    return render_template('session_key.html', session_key=session_key)

@app.route('/student', methods=['GET', 'POST'])
def student():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    if request.method == 'POST':
        session_key = request.form['session_key']
        data = session_storage.get(session_key)
        if not data:
            return "Invalid session key"
        session['mcqs'] = data['mcqs']
        timer = data['timer']
        return render_template('questions.html', mcqs=data['mcqs'], timer=timer)
    return render_template('student_login.html')

@app.route('/submit', methods=['POST'])
def submit():
    user_answers = request.form.to_dict()
    mcqs = session.get('mcqs', [])

    for i, mcq in enumerate(mcqs):
        user_answer = user_answers.get(str(i), "Not answered")
        mcq['user_answer'] = user_answer
        mcq['is_correct'] = user_answer.upper() == mcq['correct'].upper()

    return render_template('results.html', mcqs=mcqs)

if __name__ == "__main__":
    app.run(debug=True)
