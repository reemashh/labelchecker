from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import google.generativeai as genai
import requests
import os

app = Flask(__name__)

# Configure Gemini API
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

# Store last detailed response for "details" follow-up
last_details = {}

@app.route("/webhook", methods=["POST"])
def webhook():
    global last_details

    from_number = request.values.get('From', '')
    incoming_msg = request.values.get('Body', '').strip()
    media_count = int(request.values.get('NumMedia', 0))

    print(f"📩 Incoming WhatsApp message: {incoming_msg} | Media count: {media_count}")

    # If user requests details from last message
    if incoming_msg.lower() in ["details", "more", "explain"] and from_number in last_details:
        reply_text = last_details[from_number]
        twiml = MessagingResponse()
        twiml.message(reply_text)
        print(f"📤 Sending detailed reply to {from_number}")
        return str(twiml), 200, {'Content-Type': 'application/xml'}

    # If there's an image
    if media_count > 0:
        media_url = request.values.get('MediaUrl0')
        media_type = request.values.get('MediaContentType0')
        print(f"🖼 Received image: {media_url} ({media_type})")

        try:
            img_data = requests.get(media_url, auth=(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])).content

            # Send image to Gemini for OCR + short classification
            prompt = """Extract the list of ingredients from the image and for each ingredient, classify as:
✅ Safe – Natural and beneficial
⚠️ Caution – Artificial or could cause issues for some
❌ Avoid – Strongly advised against for health

Respond only with ingredient name, emoji, and reason (short)."""
            gemini_reply = model.generate_content(
                [{"mime_type": media_type, "data": img_data}, prompt]
            )

            short_reply = gemini_reply.text.strip() if gemini_reply.text else "Sorry, I couldn’t read that image."

            # Now also store long version for later
            detailed_prompt = """Extract all ingredients from the image and give detailed explanation for each about safety, natural/artificial status, and health risks."""
            details_resp = model.generate_content(
                [{"mime_type": media_type, "data": img_data}, detailed_prompt]
            )
            long_reply = details_resp.text.strip() if details_resp.text else "No detailed data found."

            last_details[from_number] = long_reply

            reply_text = short_reply + "\n\nSend 'details' for full explanation."

        except Exception as e:
            print(f"❌ Error handling image: {e}")
            reply_text = "Sorry, something went wrong processing the image."

    # If there's just text
    else:
        try:
            prompt = f"""Analyze the following ingredients: {incoming_msg}
Classify each as:
✅ Safe – Natural and beneficial
⚠️ Caution – Artificial or could cause issues
❌ Avoid – Strongly advised against for health

Respond only with ingredient name, emoji, and reason (short)."""
            gemini_reply = model.generate_content(prompt)
            short_reply = gemini_reply.text.strip()

            # Store long version
            details_prompt = f"Analyze these ingredients in detail: {incoming_msg}"
            details_resp = model.generate_content(details_prompt)
            last_details[from_number] = details_resp.text.strip()

            reply_text = short_reply + "\n\nSend 'details' for full explanation."
        except Exception as e:
            print(f"❌ Error from Gemini API: {e}")
            reply_text = "Sorry, something went wrong."

    twiml = MessagingResponse()
    twiml.message(reply_text)
    print(f"📤 Sending reply: {reply_text}")
    return str(twiml), 200, {'Content-Type': 'application/xml'}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
