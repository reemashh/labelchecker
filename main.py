from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import google.generativeai as genai
import requests
import os

app = Flask(__name__)

# Configure Gemini API
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

# Store last detailed response for each user
last_details = {}

def is_request_for_details(user_msg):
    """Ask Gemini if the message is a request for more details."""
    check_prompt = f"""
The user sent: "{user_msg}".
Are they asking for a more detailed or expanded explanation of previous results?
Reply with only YES or NO.
"""
    decision = model.generate_content(check_prompt).text.strip().upper()
    return decision.startswith("Y")

@app.route("/webhook", methods=["POST"])
def webhook():
    global last_details

    from_number = request.values.get('From', '')
    incoming_msg = request.values.get('Body', '').strip()
    media_count = int(request.values.get('NumMedia', 0))

    print(f"📩 Incoming WhatsApp message: {incoming_msg} | Media count: {media_count}")

    # If user asks for details about previous reply
    if from_number in last_details and is_request_for_details(incoming_msg):
        reply_text = last_details[from_number]
        twiml = MessagingResponse()
        twiml.message(reply_text)
        print(f"📤 Sending detailed reply to {from_number}")
        return str(twiml), 200, {'Content-Type': 'application/xml'}

    # If an image is sent
    if media_count > 0:
        media_url = request.values.get("MediaUrl0")
        media_type = request.values.get("MediaContentType0")
        print(f"🖼 Received image: {media_url} ({media_type})")

        try:
            img_data = requests.get(
                media_url,
                auth=(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
            ).content

            # Short summary
            prompt = f"""Extract the list of ingredients from this image and classify each as:
✅ Safe – Natural and beneficial
⚠️ Caution – Artificial or could cause issues for some
❌ Avoid – Strongly advised against for health

Respond starting with:
Quick health check on your ingredients:
Then list items briefly."""
            gemini_reply = model.generate_content(
                [{"mime_type": media_type, "data": img_data}, prompt]
            )
            short_reply = gemini_reply.text.strip() if gemini_reply.text else "Sorry, I couldn’t read that image."

            # Detailed explanation
            detailed_prompt = """Extract all ingredients from this image and give a detailed health analysis of each."""
            details_resp = model.generate_content(
                [{"mime_type": media_type, "data": img_data}, detailed_prompt]
            )
            long_reply = details_resp.text.strip() if details_resp.text else "No detailed data found."

            last_details[from_number] = long_reply
            reply_text = short_reply + "\n\nReply with 'more info' for detailed explanations."

        except Exception as e:
            print(f"❌ Error handling image: {e}")
            reply_text = "Sorry, something went wrong processing the image."

    # If it's just text (ingredient list typed by user)
    else:
        try:
            prompt = f"""Analyze the following ingredients: {incoming_msg}
Classify each as:
✅ Safe – Natural and beneficial
⚠️ Caution – Artificial or could cause issues
❌ Avoid – Strongly advised against for health

Respond starting with:
Quick health check on your ingredients:
Then list items briefly."""
            gemini_reply = model.generate_content(prompt)
            short_reply = gemini_reply.text.strip()

            details_prompt = f"Give a detailed health analysis of each ingredient in: {incoming_msg}"
            details_resp = model.generate_content(details_prompt)
            long_reply = details_resp.text.strip()

            last_details[from_number] = long_reply
            reply_text = short_reply + "\n\nReply with 'more info' for detailed explanations."

        except Exception as e:
            print(f"❌ Error from Gemini API: {e}")
            reply_text = "Sorry, something went wrong."

    # Send Twilio response
    twiml = MessagingResponse()
    twiml.message(reply_text)
    print(f"📤 Sending reply: {reply_text}")
    return str(twiml), 200, {'Content-Type': 'application/xml'}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
