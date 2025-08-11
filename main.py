from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import google.generativeai as genai
import requests
import os
import pytesseract  # OCR library
from PIL import Image
from io import BytesIO

app = Flask(__name__)

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
text_model = genai.GenerativeModel("gemini-1.5-flash")
last_analysis = {}

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming = request.values.get("Body", "").strip().lower()
    num_media = int(request.values.get("NumMedia", 0))
    sender = request.values.get("From", "")
    resp = MessagingResponse()

    if incoming in ["details", "explain", "more info"] and sender in last_analysis:
        resp.message(last_analysis[sender])
        return str(resp), 200

    if num_media > 0:
        # Download and OCR
        media_url = request.values.get("MediaUrl0")
        img = Image.open(BytesIO(requests.get(media_url).content))
        extracted_text = pytesseract.image_to_string(img)

        if not extracted_text.strip():
            resp.message("Couldn't read ingredients. Please send clear photo or type it.")
            return str(resp), 200

        ingredient_text = extracted_text
    else:
        ingredient_text = incoming

    # Classification
    classify_prompt = f"Classify these ingredients with emoji:\n{ingredient_text}"
    classify_resp = text_model.generate_content(classify_prompt)
    short = classify_resp.text.strip()

    last_analysis[sender] = text_model.generate_content(
        f"Give detailed safety analysis for each ingredient: {ingredient_text}"
    ).text.strip()

    resp.message(short)
    return str(resp), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
