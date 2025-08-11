from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import google.generativeai as genai
import os

# Flask app setup
app = Flask(__name__)

# Configure Gemini API
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle incoming WhatsApp messages from Twilio."""
    try:
        # Get incoming message text
        incoming_msg = request.values.get('Body', '').strip()
        print(f"📩 Incoming WhatsApp message: {incoming_msg}")

        # If no text sent
        if not incoming_msg:
            reply_text = "I didn’t receive any text. Please send me some ingredients or text."
        else:
            try:
                # Call Gemini API
                gemini_reply = model.generate_content(
                    f"Analyze the following food ingredients and explain if any are harmful: {incoming_msg}"
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
    twiml.message(reply_text)

    # Log reply for debugging
    print(f"📤 Sending reply to WhatsApp: {reply_text}")

    # Return TwiML XML with correct content type
    return str(twiml), 200, {'Content-Type': 'application/xml'}

if __name__ == "__main__":
    # Run locally for testing, Render/Heroku will handle prod
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
