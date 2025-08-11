import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import google.generativeai as genai

# === Config ===
TWILIO_WHATSAPP_NUMBER = os.environ.get("TWILIO_WHATSAPP_NUMBER")  # e.g. 'whatsapp:+14155238886'
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Init Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")  # free + fast

# Init Flask
app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle incoming WhatsApp message."""
    try:
        incoming_msg = request.values.get('Body', '').strip()
        print(f"📩 Incoming WhatsApp message: {incoming_msg}")

        if not incoming_msg:
            reply = "I didn’t receive any text. Please send me some ingredients or text."
        else:
            # Send to Gemini
            gemini_reply = model.generate_content(
                f"Analyze the following food ingredients and explain if any are harmful: {incoming_msg}"
            )
            reply = gemini_reply.text.strip() if gemini_reply.text else "Sorry, I couldn’t process that."

    except Exception as e:
        print(f"❌ Error from Gemini API: {e}")
        reply = "Sorry, something went wrong."

    # Send back to WhatsApp
    twiml = MessagingResponse()
    twiml.message(reply)
    return str(twiml)

@app.route("/", methods=["GET"])
def home():
    return "WhatsApp Gemini bot is running."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
