from flask import Flask, request
import openai
import os
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)
openai.api_key = os.environ["OPENAI_API_KEY"]

@app.route("/webhook", methods=["POST"])
def whatsapp_webhook():
    incoming_msg = request.values.get('Body', '').strip()
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
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        reply = completion.choices[0].message['content']
    except Exception as e:
        reply = f"Error: {str(e)}"

    msg.body(reply)
    return str(response)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
