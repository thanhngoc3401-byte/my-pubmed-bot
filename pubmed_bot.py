import logging
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from deep_translator import GoogleTranslator

# --- CẤU HÌNH ---
TELEGRAM_TOKEN = "8643595444:AAFptKJZp045zzSgf5xMCtf2WFyP0DJOKu0"
PUBMED_API_KEY = "01115b953b66629df050b91c4d77233f6008"

# Bộ nhớ để tránh trùng lặp: {user_id: [list_of_seen_pmids]}
seen_papers = {}

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def translate_to_en(text):
    return GoogleTranslator(source='auto', target='en').translate(text)

def translate_to_vi(text):
    return GoogleTranslator(source='auto', target='vi').translate(text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🌟 Chào bác sĩ! Tôi đã sẵn sàng tra cứu chuyên sâu.\n- Ưu tiên: 5 năm gần nhất.\n- Loại: Free Full Text.\n- Ngôn ngữ: Trả lời tiếng Việt.")

def get_pubmed_data(query, user_id):
    # Dịch query sang tiếng Anh để tìm kiếm chính xác
    query_en = translate_to_en(query)
    
    # Thêm filter: 5 năm gần nhất và Free Full Text
    current_year = datetime.now().year
    five_years_ago = current_year - 5
    enhanced_query = f"({query_en}) AND (free full text[filter]) AND ({five_years_ago}:{current_year}[dp])"
    
    # 1. Tìm ID bài báo (lấy nhiều hơn 3 để lọc trùng)
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed", "term": enhanced_query, "retmode": "json", 
        "retmax": 20, "api_key": PUBMED_API_KEY
    }
    
    r = requests.get(search_url, params=params).json()
    all_ids = r.get('esearchresult', {}).get('idlist', [])
    
    # Lọc bỏ các ID đã xem
    user_seen = seen_papers.get(user_id, [])
    new_ids = [i for i in all_ids if i not in user_seen][:3]
    
    if not new_ids:
        return "❌ Không tìm thấy nghiên cứu mới nào (hoặc đã hết bài báo mới cho từ khóa này)."

    # Cập nhật danh sách đã xem
    seen_papers.setdefault(user_id, []).extend(new_ids)

    # 2. Lấy chi tiết bài báo (Sử dụng efetch để lấy Abstract chi tiết hơn)
    fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    summary_params = {"db": "pubmed", "id": ",".join(new_ids), "retmode": "json", "api_key": PUBMED_API_KEY}
    
    resp = requests.get(fetch_url, params=summary_params).json()
    results = resp.get('result', {})

    final_msg = f"🔍 **Kết quả nghiên cứu (Free Full Text, 5 năm qua):**\n\n"
    
    for uid in new_ids:
        paper = results.get(uid)
        if paper:
            title_vi = translate_to_vi(paper.get('title', ''))
            pub_date = paper.get('pubdate', 'N/A')
            journal = paper.get('source', 'N/A')
            # Vị trí thông tin: Trong PubMed thường trả về cấu trúc Volume, Issue, Pages
            location = f"Tạp chí {journal}, Tập {paper.get('volume', 'N/A')}, Trang {paper.get('pages', 'N/A')}"
            
            final_msg += f"✅ **{title_vi}**\n"
            final_msg += f"📅 XB: {pub_date}\n"
            final_msg += f"📍 Vị trí: {location}\n"
            final_msg += f"🔗 Link: https://pubmed.ncbi.nlm.nih.gov/{uid}/\n"
            final_msg += "──────────────────\n"
            
    return final_msg

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.message.text
    await update.message.reply_chat_action("typing")
    
    response = get_pubmed_data(query, user_id)
    await update.message.reply_text(response, parse_mode="Markdown", disable_web_page_preview=True)

if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
