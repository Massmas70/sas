# -*- coding: utf-8 -*-

import os
import psycopg2
from telegram import *
from telegram.ext import *

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# ---------------- DB ----------------
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

def admin_menu():
    return ReplyKeyboardMarkup([
        ["📊 الإحصائيات", "📅 إحصائيات الشهر"],
        ["👥 المستخدمين", "🗄️ قاعدة البيانات"],
        ["📢 إذاعة"],
        ["🔙 رجوع"]
    ], resize_keyboard=True)

def back_admin():
    return ReplyKeyboardMarkup([["🔙 رجوع"]], resize_keyboard=True)

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
    context.user_data["admin"] = True
    update.message.reply_text("🔧 لوحة الأدمن", reply_markup=admin_menu())

# ---------------- حساباتي (أزرار شفافة) ----------------
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

    update.message.reply_text("📂 حساباتك:", reply_markup=InlineKeyboardMarkup(keyboard))

# ---------------- عرض مستخدمين (أدمن) ----------------
def admin_users(update, context):
    cursor.execute("SELECT user_id FROM users LIMIT 20")
    users = cursor.fetchall()

    keyboard = [
        [InlineKeyboardButton(str(u[0]), callback_data=f"user_{u[0]}")]
        for u in users
    ]

    keyboard.append([InlineKeyboardButton("🔍 بحث", callback_data="search_user")])

    update.message.reply_text("👥 المستخدمين:", reply_markup=InlineKeyboardMarkup(keyboard))

# ---------------- CALLBACK ----------------
def button(update, context):
    query = update.callback_query
    query.answer()
    data = query.data

    # حساب
    if data.startswith("acc_"):
        acc_id = int(data.split("_")[1])

        cursor.execute("SELECT username, password, balance FROM accounts WHERE id=%s", (acc_id,))
        acc = cursor.fetchone()

        context.user_data["account_id"] = acc_id

        keyboard = [
            [InlineKeyboardButton("➕ تعبئة", callback_data="deposit_acc"),
             InlineKeyboardButton("➖ سحب", callback_data="withdraw_acc")],
            [InlineKeyboardButton("❌ حذف", callback_data="delete")],
            [InlineKeyboardButton("🔑 تغيير كلمة السر", callback_data="change_pass")]
        ]

        query.edit_message_text(
            f"👤 {acc[0]}\n🔑 {acc[1]}\n💰 {acc[2]}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # عرض مستخدم
    elif data.startswith("user_"):
        uid = int(data.split("_")[1])

        cursor.execute("SELECT wallet FROM users WHERE user_id=%s", (uid,))
        wallet = cursor.fetchone()

        cursor.execute("SELECT COUNT(*) FROM accounts WHERE user_id=%s", (uid,))
        accs = cursor.fetchone()[0]

        query.edit_message_text(
            f"👤 المستخدم: {uid}\n💰 المحفظة: {wallet[0] if wallet else 0}\n📂 الحسابات: {accs}"
        )

    elif data == "search_user":
        context.user_data["step"] = "search_user"
        query.message.reply_text("🔍 أرسل ID المستخدم:")

# ---------------- الرسائل ----------------
def handle_message(update, context):
    user_id = update.effective_user.id
    text = update.message.text
    step = context.user_data.get("step")

    # رجوع
    if text == "🔙 رجوع":
        if context.user_data.get("admin"):
            update.message.reply_text("🔧 لوحة الأدمن", reply_markup=admin_menu())
        else:
            update.message.reply_text("🏠 الرئيسية", reply_markup=main_menu())
        return

    # -------- ADMIN --------
    if user_id == ADMIN_ID:

        if text == "👥 المستخدمين":
            admin_users(update, context)
            return

        elif text == "📢 إذاعة":
            context.user_data["step"] = "broadcast"
            update.message.reply_text("✉️ أرسل الرسالة:", reply_markup=back_admin())
            return

        elif text == "📊 الإحصائيات":
            cursor.execute("SELECT COUNT(*) FROM users")
            users = cursor.fetchone()[0]
            update.message.reply_text(f"👥 المستخدمين: {users}", reply_markup=admin_menu())
            return

    # بحث مستخدم
    if step == "search_user":
        try:
            uid = int(text)
        except:
            update.message.reply_text("❌ رقم غير صحيح")
            return

        cursor.execute("SELECT wallet FROM users WHERE user_id=%s", (uid,))
        data = cursor.fetchone()

        if not data:
            update.message.reply_text("❌ غير موجود")
        else:
            update.message.reply_text(f"👤 {uid}\n💰 {data[0]}")

        context.user_data["step"] = None
        return

    # بث
    if step == "broadcast":
        cursor.execute("SELECT user_id FROM users")
        for u in cursor.fetchall():
            try:
                context.bot.send_message(u[0], text)
            except:
                pass

        update.message.reply_text("✅ تم", reply_markup=admin_menu())
        context.user_data["step"] = None
        return

    # -------- USER --------

    if text == "📂 حساباتي":
        show_accounts(update, context)

    elif text == "➕ إنشاء حساب":
        context.user_data["step"] = "username"
        update.message.reply_text("👤 username:")

    elif step == "username":
        context.user_data["username"] = text
        context.user_data["step"] = "password"
        update.message.reply_text("🔑 password:")

    elif step == "password":
        cursor.execute(
            "INSERT INTO accounts (user_id, username, password) VALUES (%s,%s,%s)",
            (user_id, context.user_data["username"], text)
        )
        conn.commit()

        update.message.reply_text("✅ تم", reply_markup=main_menu())
        context.user_data.clear()

# ---------------- تشغيل ----------------
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("admin", admin_panel))
    dp.add_handler(CallbackQueryHandler(button))
    dp.add_handler(MessageHandler(Filters.text, handle_message))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
