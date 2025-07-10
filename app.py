import os
import requests
from flask import Flask, render_template, request, send_from_directory, send_file
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from PIL import Image, ImageDraw, ImageFont
import easyocr

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
RESULT_FOLDER = 'translated'
PDF_FOLDER = 'pdfs'
FONT_PATH = 'fonts/DejaVuSans.ttf'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)
os.makedirs(PDF_FOLDER, exist_ok=True)

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
        return text

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

def download_images_from_url(page_url, download_folder):
    res = requests.get(page_url)
    soup = BeautifulSoup(res.text, "html.parser")
    image_paths = []
    for img in soup.find_all("img"):
        img_url = urljoin(page_url, img.get("src"))
        try:
            img_data = requests.get(img_url).content
            filename = os.path.basename(img_url.split("?")[0])
            filepath = os.path.join(download_folder, filename)
            with open(filepath, "wb") as f:
                f.write(img_data)
            image_paths.append(filepath)
        except Exception as e:
            print(f"Failed to download {img_url}: {e}")
    return image_paths

def images_to_pdf(image_paths, output_pdf_path):
    images = [Image.open(p).convert("RGB") for p in image_paths]
    if images:
        images[0].save(output_pdf_path, save_all=True, append_images=images[1:])

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

@app.route("/translate_url", methods=["GET", "POST"])
def translate_url():
    if request.method == "POST":
        url = request.form.get("url")
        if not url:
            return "No URL provided"

        image_paths = download_images_from_url(url, UPLOAD_FOLDER)
        translated_paths = []

        for path in image_paths:
            filename = os.path.basename(path)
            output_path = os.path.join(RESULT_FOLDER, filename)
            translate_image(path, output_path)
            translated_paths.append(output_path)

        pdf_name = "translated_output.pdf"
        pdf_path = os.path.join(PDF_FOLDER, pdf_name)
        images_to_pdf(translated_paths, pdf_path)

        return send_file(pdf_path, as_attachment=True)

    return render_template("translate_url.html")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
