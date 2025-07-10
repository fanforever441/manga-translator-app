import os
import requests
from flask import Flask, render_template, request, send_from_directory
from PIL import Image, ImageDraw, ImageFont
import easyocr

# Flask setup
app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
RESULT_FOLDER = 'translated'
FONT_PATH = 'fonts/DejaVuSans.ttf'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

# LibreTranslate: Free public API
def translate_text(text):
    try:
        response = requests.post("https://libretranslate.de/translate", data={
            "q": text,
            "source": "zh",
            "target": "en",
            "format": "text"
        })
        return response.json()["translatedText"]
    except Exception as e:
        print("Translation error:", e)
        return text  # fallback to original if it fails

# Wrap text within a width limit
def wrap_text(text, font, max_width):
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        if font.getsize(current_line + " " + word)[0] <= max_width:
            current_line += " " + word
        else:
            lines.append(current_line.strip())
            current_line = word
    if current_line:
        lines.append(current_line.strip())
    return lines

# Core translation and editing function
def translate_image(image_path, output_path):
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    reader = easyocr.Reader(['ch_sim', 'en'], verbose=False)
    font = ImageFont.truetype(FONT_PATH, size=20)

    results = reader.readtext(image_path)

    for (bbox, text, prob) in results:
        if prob < 0.4 or not text.strip():
            continue

        try:
            translated = translate_text(text.strip())
        except:
            translated = text

        top_left = tuple(map(int, bbox[0]))
        bottom_right = tuple(map(int, bbox[2]))

        draw.rectangle([top_left, bottom_right], fill="white")

        box_width = bottom_right[0] - top_left[0]
        box_height = bottom_right[1] - top_left[1]

        wrapped = wrap_text(translated, font, box_width)
        total_height = len(wrapped) * font.getsize("A")[1]
        y_text = top_left[1] + (box_height - total_height) // 2

        for line in wrapped:
            line_width, _ = draw.textsize(line, font=font)
            x_text = top_left[0] + (box_width - line_width) // 2
            draw.text((x_text, y_text), line, font=font, fill="black")
            y_text += font.getsize(line)[1]

    image.save(output_path)

# Routes
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files['image']
        if file:
            filename = file.filename
            input_path = os.path.join(UPLOAD_FOLDER, filename)
            output_path = os.path.join(RESULT_FOLDER, filename)

            file.save(input_path)
            translate_image(input_path, output_path)

            return render_template("index.html", output_image=filename)
    return render_template("index.html")

@app.route("/translated/<filename>")
def translated_image(filename):
    return send_from_directory(RESULT_FOLDER, filename)
