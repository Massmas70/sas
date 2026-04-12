# -*- coding: utf-8 -*-

import os
import psycopg2
from telegram import *
from telegram.ext import *

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))

# ---------------- DB ----------------
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

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

# ---------------- MENUS ----------------
def main_menu():
    return ReplyKeyboardMarkup([
        ["📂 حساباتي", "➕ إنشاء حساب"],
        ["💰 محفظتي"],
        ["📞 الدعم"]
    ], resize_keyboard=True)

def back_menu():
    return ReplyKeyboardMarkup([["🔙 رجوع"]], resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup([
        ["📊 الإحصائيات", "📅 إحصائيات الشهر"],
        ["🗄️ قاعدة البيانات"],
        ["📢 إذاعة"],
        ["🔙 رجوع"]
    ], resize_keyboard=True)

# ---------------- START ----------------
def start(update, context):
    user_id = update.effective_user.id

    cursor.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id) VALUES (%s)", (user_id,))
        conn.commit()

    update.message.reply_text("👋 أهلا بك", reply_markup=main_menu())

# ---------------- ADMIN ----------------
def admin_panel(update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    update.message.reply_text("🔧 لوحة الأدمن", reply_markup=admin_menu())

# ---------------- الحسابات ----------------
def show_accounts(update, context):
    user_id = update.effective_user.id

    cursor.execute("SELECT id, username FROM accounts WHERE user_id=%s", (user_id,))
    accounts = cursor.fetchall()

    if not accounts:
        update.message.reply_text("❌ لا يوجد حسابات", reply_markup=back_menu())
        return

    text = "📂 حساباتك:\n\n"
    for acc in accounts:
        text += f"- {acc[1]} (ID: {acc[0]})\n"

    update.message.reply_text(text, reply_markup=back_menu())

# ---------------- الرسائل ----------------
def handle_message(update, context):
    user_id = update.effective_user.id
    text = update.message.text
    step = context.user_data.get("step")

    # رجوع
    if text == "🔙 رجوع":
        context.user_data.clear()
        update.message.reply_text("🏠 الرئيسية", reply_markup=main_menu())
        return

    # -------- ADMIN --------
    if user_id == ADMIN_ID:

        if text == "📊 الإحصائيات":
            cursor.execute("SELECT COUNT(*) FROM users")
            users = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM accounts")
            accounts = cursor.fetchone()[0]

            cursor.execute("SELECT SUM(amount) FROM stats WHERE type='deposit'")
            deposit = cursor.fetchone()[0] or 0

            cursor.execute("SELECT SUM(amount) FROM stats WHERE type='withdraw'")
            withdraw = cursor.fetchone()[0] or 0

            update.message.reply_text(
                f"📊 الإحصائيات:\n\n"
                f"👥 المستخدمين: {users}\n"
                f"📂 الحسابات: {accounts}\n"
                f"💰 المودع: {deposit}\n"
                f"💸 المسحوب: {withdraw}",
                reply_markup=admin_menu()
            )
            return

        elif text == "📅 إحصائيات الشهر":
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

            update.message.reply_text(
                f"📅 الشهر:\n💰 {deposit}\n💸 {withdraw}",
                reply_markup=admin_menu()
            )
            return

        elif text == "🗄️ قاعدة البيانات":
            cursor.execute("SELECT COUNT(*) FROM users")
            users = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM history")
            logs = cursor.fetchone()[0]

            update.message.reply_text(
                f"🗄️ DB:\n👥 {users}\n📜 {logs}",
                reply_markup=admin_menu()
            )
            return

        elif text == "📢 إذاعة":
            context.user_data["step"] = "broadcast"
            update.message.reply_text("✉️ أرسل الرسالة", reply_markup=back_menu())
            return

    # بث
    if step == "broadcast" and user_id == ADMIN_ID:
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()

        for u in users:
            try:
                context.bot.send_message(u[0], text)
            except:
                pass

        update.message.reply_text("✅ تم الإرسال", reply_markup=admin_menu())
        context.user_data.clear()
        return

    # -------- المستخدم --------

    if text == "📂 حساباتي":
        show_accounts(update, context)

    elif text == "➕ إنشاء حساب":
        context.user_data["step"] = "username"
        update.message.reply_text("👤 اكتب username:", reply_markup=back_menu())

    elif step == "username":
        context.user_data["username"] = text
        context.user_data["step"] = "password"
        update.message.reply_text("🔑 اكتب password:")

    elif step == "password":
        cursor.execute(
            "INSERT INTO accounts (user_id, username, password) VALUES (%s,%s,%s)",
            (user_id, context.user_data["username"], text)
        )
        conn.commit()

        update.message.reply_text("✅ تم إنشاء الحساب", reply_markup=main_menu())
        context.user_data.clear()

    elif text == "💰 محفظتي":
        cursor.execute("SELECT wallet FROM users WHERE user_id=%s", (user_id,))
        wallet = cursor.fetchone()[0]

        keyboard = ReplyKeyboardMarkup([
            ["➕ تعبئة", "➖ سحب"],
            ["📊 العمليات"],
            ["🔙 رجوع"]
        ], resize_keyboard=True)

        update.message.reply_text(f"💰 رصيدك: {wallet}", reply_markup=keyboard)

# ---------------- تشغيل ----------------
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("admin", admin_panel))
    dp.add_handler(MessageHandler(Filters.text, handle_message))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
