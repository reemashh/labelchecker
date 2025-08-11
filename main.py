from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import google.generativeai as genai
import os
import re

# Flask app setup
app = Flask(__name__)

# Configure Gemini API
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

# Store last ingredients for "details" requests
last_ingredients = {}

@app.route("/webhook", methods=["POST"])
def webhook():
    global last_ingredients

    incoming_msg = request.values.get('Body', '').strip()
    sender = request.values.get('From', '')
    print(f"📩 Incoming WhatsApp message from {sender}: {incoming_msg}")

    twiml = MessagingResponse()

    if not incoming_msg:
        twiml.message("I didn’t receive any text. Please send me some ingredients or text.")
        return str(twiml), 200, {'Content-Type': 'application/xml'}

    # If user asks for details
    if incoming_msg.lower() in ["details", "more", "full", "explain"]:
        if sender in last_ingredients:
            try:
                detailed_reply = model.generate_content(
                    f"Analyze the following food ingredients and explain if any are harmful: {last_ingredients[sender]}"
                )
                reply_text = detailed_reply.text.strip() if detailed_reply.text else "Sorry, no details available."
            except Exception as e:
                print(f"❌ Error from Gemini API: {e}")
                reply_text = "Sorry, something went wrong while getting details."
        else:
            reply_text = "No recent ingredients to explain. Please send some first."

        twiml.message(reply_text)
        print(f"📤 Sending reply: {reply_text}")
        return str(twiml), 200, {'Content-Type': 'application/xml'}

    # Otherwise, classify ingredients
    try:
        short_reply = model.generate_content(
            f"""Classify each of these ingredients into one of three categories:
✅ Safe – Natural & minimal processing
⚠️ Caution – Processed or synthetic but generally safe in small amounts
❌ Avoid – Synthetic or harmful, with potential health risks

Respond in this format:
Ingredient – Emoji – Short reason

Ingredients: {incoming_msg}"""
        )
        reply_text = short_reply.text.strip() if short_reply.text else "Sorry, I couldn’t classify that."

        # Save the ingredients for future "details" requests
        last_ingredients[sender] = incoming_msg

    except Exception as e:
        print(f"❌ Error from Gemini API: {e}")
        reply_text = "Sorry, something went wrong while analyzing your message."

    twiml.message(reply_text)
    print(f"📤 Sending reply: {reply_text}")
    return str(twiml), 200, {'Content-Type': 'application/xml'}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
