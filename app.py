# -*- coding: utf-8 -*-

import os
import psycopg2
from telegram import *
from telegram.ext import *

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))

# ---------------- الاتصال بقاعدة البيانات ----------------
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# ---------------- إنشاء الجداول ----------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    wallet INTEGER DEFAULT 0
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS accounts (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    username TEXT,
    password TEXT,
    balance INTEGER DEFAULT 0
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS history (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    action TEXT
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS stats (
    id SERIAL PRIMARY KEY,
    type TEXT,
    amount INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

conn.commit()

# ---------------- NAVIGATION ----------------
def push_page(context, page):
    if "nav_stack" not in context.user_data:
        context.user_data["nav_stack"] = []
    context.user_data["nav_stack"].append(page)

def pop_page(context):
    if "nav_stack" in context.user_data and len(context.user_data["nav_stack"]) > 1:
        context.user_data["nav_stack"].pop()
        return context.user_data["nav_stack"][-1]
    return "main"

# ---------------- القائمة الرئيسية ----------------
def main_menu():
    return ReplyKeyboardMarkup([
        ["📂 حساباتي", "➕ إنشاء حساب"],
        ["💰 محفظتي"],
        ["📞 الدعم"],
        ["🔙 رجوع"]
    ], resize_keyboard=True)

# ---------------- start ----------------
def start(update, context):
    user_id = update.effective_user.id

    cursor.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id) VALUES (%s)", (user_id,))
        conn.commit()

    context.user_data["nav_stack"] = ["main"]

    update.message.reply_text("👋 أهلا بك", reply_markup=main_menu())

# ---------------- لوحة الأدمن ----------------
def admin_panel(update, context):
    if update.effective_user.id != ADMIN_ID:
        return

    push_page(context, "admin")

    keyboard = [
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats")],
        [InlineKeyboardButton("📅 إحصائيات الشهر", callback_data="admin_month")],
        [InlineKeyboardButton("🗄️ قاعدة البيانات", callback_data="admin_db")],
        [InlineKeyboardButton("📢 إذاعة", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
    ]

    update.message.reply_text("🔧 لوحة الأدمن", reply_markup=InlineKeyboardMarkup(keyboard))

# ---------------- عرض الحسابات ----------------
def show_accounts(update, context):
    user_id = update.effective_user.id

    cursor.execute("SELECT id, username FROM accounts WHERE user_id=%s", (user_id,))
    accounts = cursor.fetchall()

    if not accounts:
        update.message.reply_text("❌ لا يوجد حسابات")
        return

    keyboard = [
        [InlineKeyboardButton(acc[1], callback_data=f"acc_{acc[0]}")]
        for acc in accounts
    ]

    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back")])

    update.message.reply_text("📂 حساباتك:", reply_markup=InlineKeyboardMarkup(keyboard))

# ---------------- الأزرار ----------------
def button(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    query.answer()

    # -------- رجوع ذكي --------
    if data == "back":
        prev = pop_page(context)

        if prev == "main":
            query.message.reply_text("🏠 القائمة الرئيسية", reply_markup=main_menu())

        elif prev == "accounts":
            show_accounts(update, context)

        elif prev == "wallet":
            cursor.execute("SELECT wallet FROM users WHERE user_id=%s", (user_id,))
            wallet = cursor.fetchone()[0]

            keyboard = [
                [InlineKeyboardButton("➕ تعبئة المحفظة", callback_data="deposit_wallet")],
                [InlineKeyboardButton("➖ سحب من المحفظة", callback_data="withdraw_wallet")],
                [InlineKeyboardButton("📊 العمليات", callback_data="history")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
            ]

            query.message.reply_text(
                f"💰 رصيدك: {wallet} ل.س",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        elif prev == "admin":
            admin_panel(update, context)

        return

    # -------- ADMIN --------
    if user_id == ADMIN_ID:

        if data == "admin_stats":
            cursor.execute("SELECT COUNT(*) FROM users")
            users = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM accounts")
            accounts = cursor.fetchone()[0]

            cursor.execute("SELECT SUM(amount) FROM stats WHERE type='deposit'")
            deposit = cursor.fetchone()[0] or 0

            cursor.execute("SELECT SUM(amount) FROM stats WHERE type='withdraw'")
            withdraw = cursor.fetchone()[0] or 0

            query.message.reply_text(
                f"📊 الإحصائيات:\n\n"
                f"👥 المستخدمين: {users}\n"
                f"📂 الحسابات: {accounts}\n"
                f"💰 المودع: {deposit}\n"
                f"💸 المسحوب: {withdraw}"
            )
            return

        elif data == "admin_month":
            cursor.execute("""
            SELECT SUM(amount) FROM stats
            WHERE type='deposit'
            AND date_trunc('month', created_at) = date_trunc('month', CURRENT_DATE)
            """)
            deposit = cursor.fetchone()[0] or 0

            cursor.execute("""
            SELECT SUM(amount) FROM stats
            WHERE type='withdraw'
            AND date_trunc('month', created_at) = date_trunc('month', CURRENT_DATE)
            """)
            withdraw = cursor.fetchone()[0] or 0

            query.message.reply_text(
                f"📅 إحصائيات الشهر:\n\n"
                f"💰 المودع: {deposit}\n"
                f"💸 المسحوب: {withdraw}"
            )
            return

        elif data == "admin_db":
            cursor.execute("SELECT COUNT(*) FROM users")
            users = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM accounts")
            accounts = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM history")
            logs = cursor.fetchone()[0]

            query.message.reply_text(
                f"🗄️ قاعدة البيانات:\n\n"
                f"👥 المستخدمين: {users}\n"
                f"📂 الحسابات: {accounts}\n"
                f"📜 العمليات: {logs}"
            )
            return

        elif data == "admin_broadcast":
            context.user_data["step"] = "admin_broadcast"
            query.message.reply_text("✉️ أرسل الرسالة الآن:")
            return

    # -------- الحساب --------
    if data.startswith("acc_"):
        acc_id = int(data.split("_")[1])
        context.user_data["account_id"] = acc_id
        push_page(context, "accounts")

        cursor.execute("SELECT username, password, balance FROM accounts WHERE id=%s", (acc_id,))
        acc = cursor.fetchone()

        keyboard = [
            [InlineKeyboardButton("➕ تعبئة", callback_data="deposit_acc"),
             InlineKeyboardButton("➖ سحب", callback_data="withdraw_acc")],
            [InlineKeyboardButton("❌ حذف", callback_data="delete")],
            [InlineKeyboardButton("🔑 تغيير كلمة السر", callback_data="change_pass")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
        ]

        query.edit_message_text(
            f"👤 {acc[0]}\n🔑 {acc[1]}\n💰 {acc[2]} ل.س",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ---------------- الرسائل ----------------
def handle_message(update, context):
    user_id = update.effective_user.id
    text = update.message.text
    step = context.user_data.get("step")

    if text == "🔙 رجوع":
        prev = pop_page(context)

        if prev == "main":
            update.message.reply_text("🏠 القائمة الرئيسية", reply_markup=main_menu())

        elif prev == "accounts":
            show_accounts(update, context)

        elif prev == "wallet":
            cursor.execute("SELECT wallet FROM users WHERE user_id=%s", (user_id,))
            wallet = cursor.fetchone()[0]

            keyboard = [
                [InlineKeyboardButton("➕ تعبئة المحفظة", callback_data="deposit_wallet")],
                [InlineKeyboardButton("➖ سحب من المحفظة", callback_data="withdraw_wallet")],
                [InlineKeyboardButton("📊 العمليات", callback_data="history")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
            ]

            update.message.reply_text(
                f"💰 رصيدك: {wallet} ل.س",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return

    if text == "💰 محفظتي":
        push_page(context, "wallet")

    elif text == "📂 حساباتي":
        push_page(context, "accounts")
        show_accounts(update, context)

    elif text == "➕ إنشاء حساب":
        context.user_data["step"] = "username"
        update.message.reply_text("👤 اكتب username:")

    elif step == "username":
        context.user_data["username"] = text
        context.user_data["step"] = "password"
        update.message.reply_text("🔑 اكتب password:")

    elif step == "password":
        username = context.user_data.get("username")

        cursor.execute("""
        INSERT INTO accounts (user_id, username, password)
        VALUES (%s, %s, %s)
        """, (user_id, username, text))

        conn.commit()

        context.user_data["step"] = None
        update.message.reply_text("✅ تم إنشاء الحساب")

# ---------------- تشغيل ----------------
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("admin", admin_panel))
    dp.add_handler(MessageHandler(Filters.text, handle_message))
    dp.add_handler(CallbackQueryHandler(button))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
