from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import google.generativeai as genai
import requests
import os
from PIL import Image
from io import BytesIO

app = Flask(__name__)

# Configure Gemini API
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

# Store last detailed response for "details" follow-up
last_details = {}

def resize_image(image_bytes, max_width=1024):
    """Resize image to reduce memory usage without losing OCR quality."""
    with Image.open(BytesIO(image_bytes)) as img:
        if img.width > max_width:
            ratio = max_width / float(img.width)
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.LANCZOS)
        output = BytesIO()
        img.save(output, format="JPEG", quality=85)
        return output.getvalue()

@app.route("/webhook", methods=["POST"])
def webhook():
    global last_details

    from_number = request.values.get('From', '')
    incoming_msg = request.values.get('Body', '').strip()
    media_count = int(request.values.get('NumMedia', 0))

    print(f"📩 Incoming WhatsApp message: {incoming_msg} | Media count: {media_count}")

    # If user requests details from last message
    if incoming_msg.lower() in ["details", "more", "explain", "more info", "full info", "tell me more"] \
            and from_number in last_details:
        twiml = MessagingResponse()
        twiml.message(last_details[from_number])
        print(f"📤 Sending detailed reply to {from_number}")
        return str(twiml), 200, {'Content-Type': 'application/xml'}

    # If there's an image
    if media_count > 0:
        media_url = request.values.get('MediaUrl0')
        media_type = request.values.get('MediaContentType0')
        print(f"🖼 Received image: {media_url} ({media_type})")

        try:
            # Get and resize image to reduce memory load
            img_data = requests.get(
                media_url,
                auth=(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
            ).content
            img_data = resize_image(img_data)

            # Combined request to Gemini to get short & detailed outputs in one pass
            combined_prompt = """
Extract the list of ingredients from the image.

First, give a **short** classification:
Quick health check on your ingredients:
✅ Safe – Natural and beneficial
⚠️ Caution – Artificial or could cause issues for some
❌ Avoid – Strongly advised against for health

Respond with ingredient name, emoji, and short reason.

Then, provide a **detailed** explanation for each ingredient:
Include safety, whether it's natural/artificial, and any health risks.
"""
            gemini_reply = model.generate_content(
                [{"mime_type": media_type, "data": img_data}, combined_prompt]
            )

            # Split short and long parts if Gemini outputs them sequentially
            if gemini_reply.text:
                parts = gemini_reply.text.strip().split("\n\n", 1)
                short_reply = parts[0]
                long_reply = parts[1] if len(parts) > 1 else "No detailed data found."
            else:
                short_reply = "Sorry, I couldn’t read that image."
                long_reply = "No detailed data found."

            last_details[from_number] = long_reply
            reply_text = short_reply + "\n\nSend 'details' for full explanation."

            # Free memory
            del img_data

        except Exception as e:
            print(f"❌ Error handling image: {e}")
            reply_text = "Sorry, something went wrong processing the image."

    # If there's just text
    else:
        try:
            short_prompt = f"""
Quick health check on your ingredients:
Analyze the following ingredients: {incoming_msg}
✅ Safe – Natural and beneficial
⚠️ Caution – Artificial or could cause issues
❌ Avoid – Strongly advised against for health
Respond with ingredient name, emoji, and short reason.
"""
            gemini_reply = model.generate_content(short_prompt)
            short_reply = gemini_reply.text.strip()

            details_prompt = f"""
Analyze these ingredients in detail: {incoming_msg}
Include safety, natural/artificial status, and health risks.
"""
            details_resp = model.generate_content(details_prompt)
            long_reply = details_resp.text.strip()

            last_details[from_number] = long_reply
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
