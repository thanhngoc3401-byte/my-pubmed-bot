import logging
import requests
import os
import threading
from flask import Flask
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from deep_translator import GoogleTranslator

# --- SERVER TÍ HON ĐỂ RENDER KHÔNG TẮT BOT ---
app_web = Flask(__name__)
@app_web.route('/')
def home(): return "Bot is running!"

def run_flask():
    app_web.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

# --- CẤU HÌNH BOT CỦA BẠN ---
TELEGRAM_TOKEN = "8699849501:AAEx-GG2lFJtT7t7o4je-eOHSGbYzR1vdhM"
PUBMED_API_KEY = "01115b953b66629df050b91c4d77233f6008"
seen_papers = {}

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def translate_to_en(text): return GoogleTranslator(source='auto', target='en').translate(text)
def translate_to_vi(text): return GoogleTranslator(source='auto', target='vi').translate(text)

def get_pubmed_data(query, user_id):
    query_en = translate_to_en(query)
    current_year = datetime.now().year
    five_years_ago = current_year - 5
    enhanced_query = f"({query_en}) AND (free full text[filter]) AND ({five_years_ago}:{current_year}[dp])"
    
    try:
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        r = requests.get(search_url, params={"db": "pubmed", "term": enhanced_query, "retmode": "json", "retmax": 15, "api_key": PUBMED_API_KEY}).json()
        all_ids = r.get('esearchresult', {}).get('idlist', [])
        
        user_seen = seen_papers.get(user_id, [])
        new_ids = [i for i in all_ids if i not in user_seen][:3]
        
        if not new_ids: return "❌ Không tìm thấy nghiên cứu mới nào."
        seen_papers.setdefault(user_id, []).extend(new_ids)

        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        resp = requests.get(fetch_url, params={"db": "pubmed", "id": ",".join(new_ids), "retmode": "json", "api_key": PUBMED_API_KEY}).json()
        results = resp.get('result', {})

        final_msg = f"🔍 **Kết quả (5 năm qua, Free Full Text):**\n\n"
        for uid in new_ids:
            paper = results.get(uid)
            if paper:
                title_vi = translate_to_vi(paper.get('title', ''))
                final_msg += f"✅ **{title_vi}**\n📅 XB: {paper.get('pubdate')}\n📍 Vị trí: {paper.get('source')}, Vol: {paper.get('volume')}, Page: {paper.get('pages')}\n🔗 Link: https://pubmed.ncbi.nlm.nih.gov/{uid}/\n──────────────────\n"
        return final_msg
    except: return "⚠️ Có lỗi xảy ra."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_chat_action("typing")
    response = get_pubmed_data(update.message.text, update.effective_user.id)
    await update.message.reply_text(response, parse_mode="Markdown", disable_web_page_preview=True)

if __name__ == "__main__":
    # Chạy server web song song với bot
    threading.Thread(target=run_flask).start()
    # Chạy bot Telegram
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()
