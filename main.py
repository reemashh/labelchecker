from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import google.generativeai as genai
import os
import requests
from PIL import Image
from io import BytesIO
import pytesseract

# Flask app setup
app = Flask(__name__)

# Configure Gemini API
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model_text = genai.GenerativeModel("gemini-1.5-flash")

# Store previous context (for a single user demo; in prod use DB or Redis)
last_context = {
    "short_summary": None,
    "detailed_info": None
}

@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle incoming WhatsApp messages from Twilio."""
    incoming_msg = request.values.get('Body', '').strip()
    media_count = int(request.values.get("NumMedia", 0))

    print(f"📩 Incoming WhatsApp message: {incoming_msg} | Media count: {media_count}")

    reply_text = ""

    try:
        # If image is sent
        if media_count > 0:
            media_url = request.values.get("MediaUrl0")
            print(f"🖼 Received image: {media_url}")

            # Download and OCR
            response = requests.get(media_url, auth=(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"]))
            img = Image.open(BytesIO(response.content))
            ocr_text = pytesseract.image_to_string(img)

            print(f"📜 OCR Extracted Text: {ocr_text}")
            ingredients_text = extract_ingredients(ocr_text)

            if not ingredients_text:
                reply_text = "I couldn't find an ingredients list in that image."
            else:
                reply_text, detailed_info = analyze_ingredients(ingredients_text)
                last_context["short_summary"] = reply_text
                last_context["detailed_info"] = detailed_info

        else:
            # If the user might be asking for details
            if last_context["short_summary"] and last_context["detailed_info"]:
                if is_request_for_details(incoming_msg):
                    reply_text = last_context["detailed_info"]
                else:
                    # Fresh ingredient text
                    reply_text, detailed_info = analyze_ingredients(incoming_msg)
                    last_context["short_summary"] = reply_text
                    last_context["detailed_info"] = detailed_info
            else:
                reply_text, detailed_info = analyze_ingredients(incoming_msg)
                last_context["short_summary"] = reply_text
                last_context["detailed_info"] = detailed_info

    except Exception as e:
        print(f"❌ Webhook error: {e}")
        reply_text = "Sorry, something went wrong."

    # Send Twilio response
    twiml = MessagingResponse()
    twiml.message(reply_text)
    print(f"📤 Sending reply: {reply_text}")
    return str(twiml), 200, {'Content-Type': 'application/xml'}

def extract_ingredients(text):
    """Find the ingredients list from OCR text."""
    lines = text.splitlines()
    for line in lines:
        if "ingredient" in line.lower():
            return line.split(":", 1)[-1].strip()
    return None

def analyze_ingredients(ingredients_text):
    """Ask Gemini for short + detailed breakdown."""
    prompt_short = f"""
Analyze these food ingredients: {ingredients_text}.
Respond with a short, friendly health check in this format:
Quick health check on your ingredients:
- [Ingredient] – [✅/⚠️/❌] – [very brief reason]
End with: 'Reply with "more info" for detailed explanations.'
"""
    prompt_detailed = f"""
Analyze these food ingredients: {ingredients_text}.
Give a detailed health analysis of each ingredient.
"""

    short_reply = model_text.generate_content(prompt_short).text.strip()
    detailed_reply = model_text.generate_content(prompt_detailed).text.strip()

    return short_reply, detailed_reply

def is_request_for_details(user_msg):
    """Use Gemini to decide if user wants more info."""
    check_prompt = f"""
The user sent: "{user_msg}".
Decide if they are asking for more details or an expanded explanation.
Respond only with YES or NO.
"""
    decision = model_text.generate_content(check_prompt).text.strip().upper()
    return decision.startswith("Y")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
