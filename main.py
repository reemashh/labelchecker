from flask import Flask, request
import os
import google.generativeai as genai
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

# Configure Gemini API
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

@app.route("/webhook", methods=["POST"])
def whatsapp_webhook():
    incoming_msg = request.values.get('Body', '').strip()
    print(f"📩 Incoming WhatsApp message: {incoming_msg}")

    response = MessagingResponse()
    msg = response.message()

    prompt = f"""
Classify the following ingredients:
{incoming_msg}

✅ Safe  
⚠️ Caution  
❌ Avoid

Examples:
- INS 211 – ❌ Avoid – Linked to hyperactivity  
- Maltodextrin – ⚠️ Caution – High glycemic index  
- Turmeric – ✅ Safe – Natural anti-inflammatory
"""

    try:
        model = genai.GenerativeModel("gemini-pro")
        completion = model.generate_content(prompt)
        reply = completion.text.strip()
    except Exception as e:
        print(f"❌ Error from Gemini API: {e}")
        reply = "Sorry, something went wrong."

    msg.body(reply)
    return str(response)

if __name__ == "__main__":
    app.run()
