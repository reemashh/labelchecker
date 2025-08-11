from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import google.generativeai as genai
import os

app = Flask(__name__)

# Configure Gemini API
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

MAX_CHARS = 1500
last_request = {}  # store last full reply for each user

def send_long_message(resp, text):
    for i in range(0, len(text), MAX_CHARS):
        resp.message(text[i:i+MAX_CHARS])

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        incoming_msg = request.values.get('Body', '').strip()
        from_number = request.values.get('From', '')  # unique per user
        print(f"📩 Incoming from {from_number}: {incoming_msg}")

        if not incoming_msg:
            reply_text = "Please send me some ingredients."
        elif incoming_msg.lower() == "details":
            # Send the stored detailed reply
            reply_text = last_request.get(from_number, "No details available. Please send ingredients first.")
        else:
            try:
                # Short classification reply
                short_reply = model.generate_content(
                    f"For each ingredient in '{incoming_msg}', classify as one of:\n"
                    "✅ Safe\n⚠️ Caution\n❌ Avoid\n"
                    "Format: Ingredient – Emoji – Very short reason (max 8 words). No extra text."
                )
                short_text = short_reply.text.strip() if short_reply.text else "Could not classify."

                # Store detailed reply for later
                detailed_reply = model.generate_content(
                    f"Analyze the following food ingredients in detail:\n{incoming_msg}\n"
                    "Explain potential benefits and risks."
                )
                last_request[from_number] = detailed_reply.text.strip() if detailed_reply.text else "No details."

                reply_text = short_text + "\n\nSend 'details' for full explanation."
            except Exception as e:
                print(f"❌ Gemini API error: {e}")
                reply_text = "Sorry, something went wrong while analyzing your message."
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        reply_text = "Sorry, an unexpected error occurred."

    twiml = MessagingResponse()
    send_long_message(twiml, reply_text)
    print(f"📤 Sending to WhatsApp: {reply_text[:100]}...")
    return str(twiml), 200, {'Content-Type': 'application/xml'}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
