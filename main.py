from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import google.generativeai as genai
import requests
import os

app = Flask(__name__)

# Configure Gemini API
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
text_model = genai.GenerativeModel("gemini-1.5-flash")  # text only
vision_model = genai.GenerativeModel("gemini-1.5-pro-vision")  # text + image

# Store last analysis for details request
last_analysis = {}

@app.route("/webhook", methods=["POST"])
def webhook():
    global last_analysis

    try:
        incoming_msg = request.values.get("Body", "").strip().lower()
        num_media = int(request.values.get("NumMedia", 0))
        print(f"📩 Incoming WhatsApp message: {incoming_msg} | Media count: {num_media}")

        reply_text = ""

        if incoming_msg == "details" and "details" in last_analysis:
            reply_text = last_analysis["details"]

        else:
            if num_media > 0:
                # Get the first image
                media_url = request.values.get("MediaUrl0")
                content_type = request.values.get("MediaContentType0")
                print(f"🖼 Received image: {media_url} ({content_type})")

                # Download image
                img_data = requests.get(media_url).content

                # Ask Gemini to read & classify
                prompt = """
                You are an expert in food safety.
                1. Read all ingredients from the image of a food package label.
                2. Classify each ingredient as:
                   ✅ Safe – Natural and generally harmless.
                   ⚠️ Caution – Processed or with potential mild health concerns.
                   ❌ Avoid – Harmful or linked to significant health risks.
                3. Only return the classification list in short form.
                """
                result = vision_model.generate_content([prompt, {"mime_type": content_type, "data": img_data}])

                reply_text = result.text.strip() if result.text else "Sorry, I couldn’t read the image."

                # Save details for later
                details_prompt = f"Provide detailed safety analysis for each ingredient found in this image: {result.text}"
                details_result = text_model.generate_content(details_prompt)
                last_analysis["details"] = details_result.text.strip()

            else:
                # Text ingredient list
                classification_prompt = f"""
                Classify the following ingredients as:
                ✅ Safe – Natural and generally harmless.
                ⚠️ Caution – Processed or with potential mild health concerns.
                ❌ Avoid – Harmful or linked to significant health risks.
                Ingredients: {incoming_msg}
                """
                class_result = text_model.generate_content(classification_prompt)
                reply_text = class_result.text.strip()

                # Save details for later
                details_prompt = f"Provide detailed safety analysis for each ingredient: {incoming_msg}"
                details_result = text_model.generate_content(details_prompt)
                last_analysis["details"] = details_result.text.strip()

    except Exception as e:
        print(f"❌ Webhook error: {e}")
        reply_text = "Sorry, something went wrong."

    # Twilio response
    twiml = MessagingResponse()
    twiml.message(reply_text)
    print(f"📤 Sending reply: {reply_text}")
    return str(twiml), 200, {"Content-Type": "application/xml"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
