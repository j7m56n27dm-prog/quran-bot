import os
import logging
import sqlite3
import random
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from flask import Flask
from threading import Thread

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8093022789:AAF2Q7GP44-VVvPgcocxEMMFww-vkv-2RqU")

# Flask server
app = Flask(__name__)

@app.route('/')
def home():
    return "🕌 Qur'on Bot ishlamoqda...", 200

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    app.run(host='0.0.0.0', port=8000)

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== DATABASE ====================
def init_db():
    conn = sqlite3.connect('quran_bot.db', check_same_thread=False)
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, 
                  username TEXT,
                  first_name TEXT,
                  score INTEGER DEFAULT 0,
                  total_questions INTEGER DEFAULT 0,
                  created_date TEXT)''')
    
    # Questions table
    c.execute('''CREATE TABLE IF NOT EXISTS questions
                 (id INTEGER PRIMARY KEY,
                  juz_number INTEGER,
                  sura_name TEXT,
                  question_text TEXT,
                  correct_answer TEXT)''')
    
    conn.commit()
    conn.close()

def seed_questions():
    conn = sqlite3.connect('quran_bot.db', check_same_thread=False)
    c = conn.cursor()
    
    # Clear existing questions
    c.execute("DELETE FROM questions")
    
    # Har bir juz uchun 15-20 ta savol
    questions_data = []
    
    # Juz 1 - 20 ta savol
    for i in range(1, 21):
        questions_data.append((len(questions_data)+1, 1, "Al-Fatiha", f"Al-Fatiha {i}-oyat", "Al-Fatiha"))
    
    # Juz 2 - 15 ta savol
    for i in range(1, 16):
        questions_data.append((len(questions_data)+1, 2, "Al-Baqara", f"Al-Baqara {i}-oyat", "Al-Baqara"))
    
    # Juz 3 - 15 ta savol
    for i in range(1, 16):
        questions_data.append((len(questions_data)+1, 3, "Ali-Imran", f"Ali-Imran {i}-oyat", "Ali-Imran"))
    
    # Juz 16-20 - har biri 10 ta savol
    for juz in range(16, 21):
        for i in range(1, 11):
            sura = "Maryam" if juz == 16 else "Taha" if juz == 17 else "Ya-Sin" if juz == 18 else "Ar-Rahman" if juz == 19 else "Al-Waqi'a"
            questions_data.append((len(questions_data)+1, juz, sura, f"{sura} {i}-oyat", sura))
    
    # Juz 21-30 - har biri 10 ta savol
    for juz in range(21, 31):
        for i in range(1, 11):
            sura = "Al-Mulk" if juz == 29 else "An-Nas" if juz == 30 else f"Sura-{juz}"
            questions_data.append((len(questions_data)+1, juz, sura, f"{sura} {i}-oyat", sura))
    
    for question in questions_data:
        c.execute("INSERT OR IGNORE INTO questions VALUES (?, ?, ?, ?, ?)", question)
    
    conn.commit()
    conn.close()
    logger.info(f"✅ {len(questions_data)} ta savol bazaga qo'shildi")

# ==================== BOT CLASS ====================
class QuranBot:
    def __init__(self):
        self.SURAS = [
            "Al-Fatiha", "Al-Baqara", "Ali-Imran", "An-Nisa", "Al-Ma'ida",
            "Al-An'am", "Al-A'raf", "Al-Anfal", "At-Tawba", "Yunus",
            "Hud", "Yusuf", "Ar-Ra'd", "Ibrahim", "Al-Hijr",
            "An-Nahl", "Al-Isra", "Al-Kahf", "Maryam", "Taha",
            "Al-Anbiya", "Al-Hajj", "Al-Mu'minun", "An-Nur", "Al-Furqan",
            "Ash-Shu'ara", "An-Naml", "Al-Qasas", "Al-Ankabut", "Ar-Rum",
            "Luqman", "As-Sajda", "Al-Ahzab", "Saba", "Fatir",
            "Ya-Sin", "As-Saffat", "Sad", "Az-Zumar", "Ghafir",
            "Fussilat", "Ash-Shura", "Az-Zukhruf", "Ad-Dukhan", "Al-Jathiya",
            "Al-Ahqaf", "Muhammad", "Al-Fath", "Al-Hujurat", "Qaf",
            "Adh-Dhariyat", "At-Tur", "An-Najm", "Al-Qamar", "Ar-Rahman",
            "Al-Waqi'a", "Al-Hadid", "Al-Mujadila", "Al-Hashr", "Al-Mumtahana",
            "As-Saff", "Al-Jumu'a", "Al-Munafiqun", "At-Taghabun", "At-Talaq",
            "At-Tahrim", "Al-Mulk", "Al-Qalam", "Al-Haqqa", "Al-Ma'arij",
            "Nuh", "Al-Jinn", "Al-Muzzammil", "Al-Muddathir", "Al-Qiyama",
            "Al-Insan", "Al-Mursalat", "An-Naba", "An-Nazi'at", "Abasa",
            "At-Takwir", "Al-Infitar", "Al-Mutaffifin", "Al-Inshiqaq", "Al-Buruj",
            "At-Tariq", "Al-A'la", "Al-Gashiya", "Al-Fajr", "Al-Balad",
            "Ash-Shams", "Al-Layl", "Ad-Duha", "Ash-Sharh", "At-Tin",
            "Al-Alaq", "Al-Qadr", "Al-Bayyina", "Az-Zalzala", "Al-Adiyat",
            "Al-Qari'a", "At-Takasur", "Al-Asr", "Al-Humaza", "Al-Fil",
            "Quraysh", "Al-Ma'un", "Al-Kawthar", "Al-Kafirun", "An-Nasr",
            "Al-Masad", "Al-Ikhlas", "Al-Falaq", "An-Nas"
        ]
        self.JUZ_LIST = [f"{i}-pora" for i in range(1, 31)]
        self.user_states = {}
        
        # Qur'oniy hikmatlar va motivatsion gaplar
        self.QURAN_QUOTES = [
            "📖 \"Qur'on - qalblarga nur, dillar uchun shifo.\"",
            "🌿 \"Kim Qur'onni o'qisa, Alloh uni ezgulik bilan to'ldiradi.\"", 
            "🕊 \"Qur'on sizni eng to'g'ri yo'lga boshlaydi.\" (Isro:9)",
            "💫 \"Kim Qur'on bilan yashasa, qalbi tinchlik topadi.\"",
            "🌸 \"Qur'on - Allohning sizga bevosita so'zi.\"",
            "✨ \"Har bir oyatni o'rganish - Allohga yaqinlashishdir.\"",
            "🌙 \"Qur'on o'qigan har bir harf uchun mukofot bor.\"",
            "🕌 \"Qur'on - hayotingizning yo'lnomasi.\"",
            "💖 \"Qur'onni o'rganish - eng yaxshi sarmoya.\"",
            "🌟 \"Qur'on bilan birga bo'lgan qalb hech qachon yolg'iz emas.\"",
            "🕋 \"Qur'on - insoniyatga rahmat.\"",
            "🌺 \"Qur'onni o'rgangan kishi eng boy odamdir.\"",
            "💎 \"Qur'on bilimi - eng qimmat baxo.\"",
            "🕯 \"Qur'on - qorong'ulikdagi nur.\"",
            "🌅 \"Har safar Qur'on o'qiganda, yangi ma'no topasiz.\""
        ]
        
        self.MOTIVATION_CORRECT = [
            "✅ *Allohu Akbar!* To'g'ri javob! Siz Qur'on bilimingizni oshiryapsiz! 🌟",
            "✅ *Mashallah!* Ajoyib javob! Davom eting, Alloh sizni rag'batlantiradi! 🏆",
            "✅ *Subhanallah!* Sizning bilimingizdan hayratdaman! Qur'on sizga baraka keltiradi! 🌿",
            "✅ *Tabarakallah!* Juda zo'r! Har to'g'ri javob sizni Jannatga yaqinlashtiradi! 🌺",
            "✅ *Alloh sizdan rozi bo'lsin!* Aql va diqqatingizga hayratdaman! 💫",
            "✅ *Barakallahu fik!* Sizning bilimingiz umringizga baraka keltiradi! 🌟",
            "✅ *Jazakallahu khayran!* Alloh sizga yaxshilik bersin! 🌸"
        ]
        
        self.MOTIVATION_INCORRECT = [
            "❌ *Sabr qiling!* Har bir noto'g'ri javob yangi o'rganish imkoniyatidir. 🌱",
            "❌ *Irodaingiz mustahkam!* Qur'on o'rganish - safar, hamma narsani bir zumda bilib bo'lmaydi. 🚶‍♂️",
            "❌ *Umidingizni yo'qotmang!* Payg'ambarimiz (s.a.v): 'Eng yaxshilariz Qur'onni o'rgangan va o'rgatganlardir' dedi. 📚",
            "❌ *Davom eting!* Har bir urinish - Alloh yo'lida qadam. Alloh chidamlilarni sevadi. 💝",
            "❌ *Tayyorgarlik jarayoni!* Bugun bilmasang, ertaga bilasan. Muhimi - istak va iroda. 🌄",
            "❌ *Rahmatli yo'l!* Qur'on o'rganish - Allohning rahmatiga olib boradigan yo'l. 🛤",
            "❌ *Yangidan boshlash!* Har bir xato - yangi boshlanish uchun imkoniyat. 🌅"
        ]
        
    def get_main_menu(self):
        return ReplyKeyboardMarkup([
            ["📝 Matnli Sinov", "🎧 Audio Sinovi"],
            ["🏆 Reyting", "📊 Statistika", "📖 Ma'lumot"]
        ], resize_keyboard=True)
    
    def get_juz_menu(self):
        keyboard = []
        row = []
        for i, juz in enumerate(self.JUZ_LIST, 1):
            row.append(KeyboardButton(juz))
            if i % 5 == 0:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([KeyboardButton("⬅️ Ortga")])
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_options_keyboard(self, correct_answer):
        wrong_answers = random.sample([s for s in self.SURAS if s != correct_answer], 3)
        options = [correct_answer] + wrong_answers
        random.shuffle(options)
        
        keyboard = [[KeyboardButton(opt)] for opt in options]
        keyboard.append([KeyboardButton("⬅️ Ortga")])
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_random_question(self, juz_number):
        conn = sqlite3.connect('quran_bot.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT * FROM questions WHERE juz_number=? ORDER BY RANDOM() LIMIT 1", (juz_number,))
        result = c.fetchone()
        conn.close()
        
        if result:
            return {
                'id': result[0],
                'juz': result[1],
                'sura': result[2],
                'text': result[3],
                'correct': result[4]
            }
        return None
    
    def update_user_stats(self, user_id, is_correct):
        conn = sqlite3.connect('quran_bot.db', check_same_thread=False)
        c = conn.cursor()
        
        c.execute('''INSERT OR IGNORE INTO users (user_id, created_date) 
                     VALUES (?, ?)''', (user_id, datetime.now().strftime("%Y-%m-%d")))
        
        if is_correct:
            c.execute('''UPDATE users SET score = score + 1, total_questions = total_questions + 1 
                         WHERE user_id = ?''', (user_id,))
        else:
            c.execute('''UPDATE users SET total_questions = total_questions + 1 
                         WHERE user_id = ?''', (user_id,))
        
        conn.commit()
        conn.close()
    
    def get_user_stats(self, user_id):
        conn = sqlite3.connect('quran_bot.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT score, total_questions FROM users WHERE user_id=?", (user_id,))
        result = c.fetchone()
        conn.close()
        
        if result:
            return {'score': result[0], 'total': result[1]}
        return {'score': 0, 'total': 0}

# Bot instance
quran_bot = QuranBot()

# ==================== TELEGRAM HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    conn = sqlite3.connect('quran_bot.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO users 
                 (user_id, username, first_name, created_date) 
                 VALUES (?, ?, ?, ?)''', 
              (user.id, user.username, user.first_name, datetime.now().strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()
    
    welcome_text = f"""🕌 *Assalomu alaykum {user.first_name}!*

*Qur'on Sinov Botiga xush kelibsiz!*

{random.choice(quran_bot.QURAN_QUOTES)}

📚 *Bot imkoniyatlari:*
• 📝 Matnli test (oyat matnini ko'rib surani toping)
• 🎧 Audio test (oyatni tinglab surani toping)
• 📖 30 pora (juz) asosida testlar
• 🏆 Ballar tizimi va statistika
• 📊 Kunlik natijalaringiz

*Har bir to'g'ri javob sizni Allohga yaqinlashtiradi!* 🌟

*Marhamat, sinov turini tanlang:*"""
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=quran_bot.get_main_menu(),
        parse_mode='Markdown'
    )

async def handle_text_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    quran_bot.user_states[user_id] = {'mode': 'text'}
    
    await update.message.reply_text(
        "📝 *Matnli sinov uchun pora tanlang:*\n\n"
        "Qur'on 30 pora (juz)dan iborat. O'zingiz istagan porani tanlang:\n\n"
        f"{random.choice(quran_bot.QURAN_QUOTES)}",
        reply_markup=quran_bot.get_juz_menu(),
        parse_mode='Markdown'
    )

async def handle_audio_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎧 *Audio sinov tez orada qo'shiladi!*\n\n"
        "Hozircha matnli testdan foydalaning 📝\n\n"
        f"{random.choice(quran_bot.QURAN_QUOTES)}",
        reply_markup=quran_bot.get_main_menu(),
        parse_mode='Markdown'
    )

async def handle_juz_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    juz_number = int(update.message.text.split('-')[0])
    
    if user_id not in quran_bot.user_states:
        quran_bot.user_states[user_id] = {'mode': 'text'}
    
    question = quran_bot.get_random_question(juz_number)
    
    if not question:
        await update.message.reply_text(
            f"❌ {juz_number}-porada hozircha savollar mavjud emas.\n"
            f"Iltimos, boshqa porani tanlang.\n\n"
            f"{random.choice(quran_bot.QURAN_QUOTES)}",
            reply_markup=quran_bot.get_juz_menu()
        )
        return
    
    quran_bot.user_states[user_id]['current_question'] = question
    
    question_text = f"""🕋 *{juz_number}-poradan savol:*

﴿{question['text']}﴾

*Bu oyat qaysi suradan?*"""
    
    await update.message.reply_text(
        question_text,
        reply_markup=quran_bot.get_options_keyboard(question['correct']),
        parse_mode='Markdown'
    )

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_answer = update.message.text
    
    if user_id not in quran_bot.user_states or 'current_question' not in quran_bot.user_states[user_id]:
        await update.message.reply_text(
            "❌ Savol topilmadi. Iltimos, yangi testni boshlang.",
            reply_markup=quran_bot.get_main_menu()
        )
        return
    
    current_question = quran_bot.user_states[user_id]['current_question']
    correct_answer = current_question['correct']
    
    if user_answer == correct_answer:
        quran_bot.update_user_stats(user_id, True)
        stats = quran_bot.get_user_stats(user_id)
        
        response_text = f"""{random.choice(quran_bot.MOTIVATION_CORRECT)}

🕋 *{correct_answer}* surasidan edi.

🏆 *Statistika:*
• To'g'ri javoblar: *{stats['score']}*
• Jami savollar: *{stats['total']}*
• Foiz: *{stats['score']/stats['total']*100:.1f}%*

{random.choice(quran_bot.QURAN_QUOTES)}"""
    else:
        quran_bot.update_user_stats(user_id, False)
        
        response_text = f"""{random.choice(quran_bot.MOTIVATION_INCORRECT)}

📖 To'g'ri javob: *{correct_answer}* edi.

💫 *Payg'ambarimiz (s.a.v) dedilar:*
\"Qur'onni o'rganishga intiling, chunki u sizning uchun shafoat qiladi\"

{random.choice(quran_bot.QURAN_QUOTES)}"""
    
    if 'current_question' in quran_bot.user_states[user_id]:
        del quran_bot.user_states[user_id]['current_question']
    
    await update.message.reply_text(
        response_text,
        reply_markup=quran_bot.get_main_menu(),
        parse_mode='Markdown'
    )

async def handle_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stats = quran_bot.get_user_stats(user_id)
    
    if stats['total'] > 0:
        percentage = (stats['score'] / stats['total']) * 100
        
        if percentage >= 80:
            rank = "🎯 *A'lo daraja! Mashallah!*"
        elif percentage >= 60:
            rank = "🌟 *Yaxshi natija! Tabriklayman!*"
        elif percentage >= 40:
            rank = "📚 *O'rta daraja, yanada kuchlaning!*"
        else:
            rank = "🌱 *Boshlang'ich, muhimi - davom etish!*"
        
        rating_text = f"""🏆 *Sizning statistikaniz:*

✅ To'g'ri javoblar: *{stats['score']}*
📊 Jami savollar: *{stats['total']}*
📈 Aniqlik darajasi: *{percentage:.1f}%*

{rank}

{random.choice(quran_bot.QURAN_QUOTES)}"""
    else:
        rating_text = f"""📊 *Hali statistika mavjud emas*

Hali test ishlamagansiz. Birinchi testni boshlang! 🚀

{random.choice(quran_bot.QURAN_QUOTES)}"""
    
    await update.message.reply_text(
        rating_text,
        reply_markup=quran_bot.get_main_menu(),
        parse_mode='Markdown'
    )

async def handle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stats = quran_bot.get_user_stats(user_id)
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    stats_text = f"""📊 *Bugungi statistika:*

📅 Sana: *{today}*
✅ To'g'ri javoblar: *{stats['score']}*
❌ Noto'g'ri javoblar: *{stats['total'] - stats['score']}*
📈 Jami savollar: *{stats['total']}*

💪 *Davom eting!* Har bir savol sizni Allohga yaqinlashtiradi.

{random.choice(quran_bot.QURAN_QUOTES)}"""
    
    await update.message.reply_text(
        stats_text,
        reply_markup=quran_bot.get_main_menu(),
        parse_mode='Markdown'
    )

async def handle_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info_text = f"""📖 *Qur'on Sinov Boti haqida:*

*Xususiyatlar:*
• 📝 *Matnli Sinov* - oyat arabchasini o'qing va surani toping
• 🎧 *Audio Sinov* - oyatni tinglang va surani toping (tez orada)
• 🏆 *Reyting* - to'plagan ballaringizni ko'ring
• 📊 *Statistika* - kunlik natijalaringiz

*Ma'lumot:*
• 30 juz (pora) asosida testlar
• Har bir juzda 10-20 ta savol
• 114 suradan tanlov
• 200+ turli savollar

🌿 *Payg'ambarimiz (s.a.v) dedilar:*
\"Sizlarning eng yaxshilaringiz Qur'onni o'rgangan va o'rgatganlaringizdir.\"

{random.choice(quran_bot.QURAN_QUOTES)}

*Dasturchi:* @python_coder_bb
*Platforma:* Koyeb 🚀"""
    
    await update.message.reply_text(
        info_text,
        reply_markup=quran_bot.get_main_menu(),
        parse_mode='Markdown'
    )

async def handle_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⬅️ Bosh menyuga qaytdingiz",
        reply_markup=quran_bot.get_main_menu()
    )

async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Tushunmadim. Iltimos, menyudan tanlang!",
        reply_markup=quran_bot.get_main_menu()
    )

# ==================== MAIN ====================
def main():
    print("🚀 Qur'on Bot ishga tushirilmoqda...")
    
    # Initialize database
    init_db()
    seed_questions()
    
    # Start Flask server
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print("🌐 Flask server ishga tushdi")
    
    try:
        # Create bot application
        application = Application.builder().token(BOT_TOKEN).build()
        print("✅ Bot yaratildi")
        
        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.Regex("^📝 Matnli Sinov$"), handle_text_test))
        application.add_handler(MessageHandler(filters.Regex("^🎧 Audio Sinovi$"), handle_audio_test))
        application.add_handler(MessageHandler(filters.Regex("^🏆 Reyting$"), handle_rating))
        application.add_handler(MessageHandler(filters.Regex("^📊 Statistika$"), handle_stats))
        application.add_handler(MessageHandler(filters.Regex("^📖 Ma'lumot$"), handle_info))
        application.add_handler(MessageHandler(filters.Regex("^⬅️ Ortga$"), handle_back))
        application.add_handler(MessageHandler(filters.Regex("^\\d+-pora$"), handle_juz_selection))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer))
        
        print("🔄 Bot polling ni boshlaydi...")
        
        # Start bot
        application.run_polling()
        
    except Exception as e:
        print(f"❌ Xatolik: {e}")

if __name__ == "__main__":
    main()
