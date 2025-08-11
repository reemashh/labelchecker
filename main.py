from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import google.generativeai as genai
import os

app = Flask(__name__)

# Configure Gemini API
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

MAX_CHARS = 1500  # safe limit for Twilio WhatsApp

def send_long_message(resp, text):
    """Split long text into safe-sized WhatsApp chunks."""
    for i in range(0, len(text), MAX_CHARS):
        resp.message(text[i:i+MAX_CHARS])

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        incoming_msg = request.values.get('Body', '').strip()
        print(f"📩 Incoming WhatsApp message: {incoming_msg}")

        if not incoming_msg:
            reply_text = "I didn’t receive any text. Please send me some ingredients or text."
        else:
            try:
                gemini_reply = model.generate_content(
                    f"Analyze these food ingredients briefly. "
                    f"Use max 5 bullet points, each under 20 words. {incoming_msg}"
                )
                reply_text = gemini_reply.text.strip() if gemini_reply.text else "Sorry, I couldn’t process that."
            except Exception as e:
                print(f"❌ Error from Gemini API: {e}")
                reply_text = "Sorry, something went wrong while analyzing your message."
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        reply_text = "Sorry, an unexpected error occurred."

    # Create Twilio reply
    twiml = MessagingResponse()
    send_long_message(twiml, reply_text)

    print(f"📤 Sending reply to WhatsApp: {reply_text[:100]}...")  # only log first 100 chars

    return str(twiml), 200, {'Content-Type': 'application/xml'}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
