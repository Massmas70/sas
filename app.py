# -*- coding: utf-8 -*-

import os
import psycopg2
from telegram import *
from telegram.ext import *

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))

# ---------------- الحالات ----------------
USERNAME, PASSWORD, AMOUNT, ADMIN_BROADCAST, CHANGE_PASSWORD = range(5)

# ---------------- قاعدة البيانات ----------------
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

# ---------------- القائمة الرئيسية ----------------
def main_menu():
    return ReplyKeyboardMarkup([
        ["📂 حساباتي", "➕ إنشاء حساب"],
        ["💰 محفظتي"],
        ["📞 الدعم"]
    ], resize_keyboard=True)

# ---------------- start ----------------
def start(update, context):
    user_id = update.effective_user.id

    cursor.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id) VALUES (%s)", (user_id,))
        conn.commit()

    update.message.reply_text("👋 أهلا بك", reply_markup=main_menu())

# ---------------- عرض الحسابات ----------------
def show_accounts(update, context):
    user_id = update.effective_user.id

    cursor.execute("SELECT id, username FROM accounts WHERE user_id=%s", (user_id,))
    accounts = cursor.fetchall()

    if not accounts:
        update.message.reply_text("❌ لا يوجد حسابات", reply_markup=main_menu())
        return

    keyboard = [
        [InlineKeyboardButton(acc[1], callback_data=f"acc_{acc[0]}")]
        for acc in accounts
    ]

    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])

    update.message.reply_text("📂 حساباتك:", reply_markup=InlineKeyboardMarkup(keyboard))

# ---------------- لوحة الأدمن ----------------
def admin_panel(update, context):
    if update.effective_user.id != ADMIN_ID:
        return

    keyboard = [
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats")],
        [InlineKeyboardButton("📅 إحصائيات الشهر", callback_data="admin_month")],
        [InlineKeyboardButton("🗄️ قاعدة البيانات", callback_data="admin_db")],
        [InlineKeyboardButton("📢 إذاعة", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]
    ]

    update.message.reply_text("🔧 لوحة الأدمن", reply_markup=InlineKeyboardMarkup(keyboard))

# ---------------- الأزرار ----------------
def button(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    query.answer()

    # رجوع
    if data == "back_main":
        query.message.reply_text("🏠 القائمة الرئيسية", reply_markup=main_menu())
        return

    elif data == "back_accounts":
        show_accounts(update, context)
        return

    # -------- ADMIN --------
    if user_id == ADMIN_ID:

        if data == "admin_stats":
            cursor.execute("SELECT COUNT(*) FROM users")
            users = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM accounts")
            accounts = cursor.fetchone()[0]

            query.message.reply_text(f"👥 المستخدمين: {users}\n📂 الحسابات: {accounts}")
            return

        elif data == "admin_broadcast":
            query.message.reply_text("✉️ أرسل الرسالة الآن:")
            return ADMIN_BROADCAST

    # -------- الحساب --------
    if data.startswith("acc_"):
        acc_id = int(data.split("_")[1])
        context.user_data["account_id"] = acc_id

        cursor.execute("SELECT username, password, balance FROM accounts WHERE id=%s", (acc_id,))
        acc = cursor.fetchone()

        keyboard = [
            [InlineKeyboardButton("➕ تعبئة", callback_data="deposit_acc"),
             InlineKeyboardButton("➖ سحب", callback_data="withdraw_acc")],
            [InlineKeyboardButton("🔑 تغيير كلمة السر", callback_data="change_pass")],
            [InlineKeyboardButton("❌ حذف", callback_data="delete")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_accounts")]
        ]

        query.edit_message_text(
            f"👤 {acc[0]}\n🔑 {acc[1]}\n💰 {acc[2]}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "delete":
        acc_id = context.user_data.get("account_id")
        cursor.execute("DELETE FROM accounts WHERE id=%s", (acc_id,))
        conn.commit()
        query.edit_message_text("✅ تم الحذف")

    elif data == "change_pass":
        query.message.reply_text("✏️ اكتب كلمة السر الجديدة:")
        return CHANGE_PASSWORD

    elif data in ["deposit_acc", "withdraw_acc"]:
        context.user_data["action"] = data
        query.message.reply_text("💰 اكتب المبلغ:")
        return AMOUNT

# ---------------- المحادثات ----------------

def get_username(update, context):
    context.user_data["username"] = update.message.text
    update.message.reply_text("🔑 اكتب كلمة السر:")
    return PASSWORD

def get_password(update, context):
    user_id = update.effective_user.id
    username = context.user_data.get("username")

    cursor.execute("INSERT INTO accounts (user_id, username, password) VALUES (%s, %s, %s)",
                   (user_id, username, update.message.text))
    conn.commit()

    update.message.reply_text("✅ تم إنشاء الحساب", reply_markup=main_menu())
    return ConversationHandler.END

def amount_handler(update, context):
    try:
        amount = int(update.message.text)
    except:
        update.message.reply_text("❌ رقم غير صحيح")
        return AMOUNT

    update.message.reply_text("✅ تم حفظ المبلغ")
    return ConversationHandler.END

def change_password_save(update, context):
    acc_id = context.user_data.get("account_id")

    cursor.execute("UPDATE accounts SET password=%s WHERE id=%s",
                   (update.message.text, acc_id))
    conn.commit()

    update.message.reply_text("✅ تم تغيير كلمة السر")
    return ConversationHandler.END

def admin_broadcast_send(update, context):
    text = update.message.text

    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()

    for u in users:
        try:
            context.bot.send_message(chat_id=u[0], text=text)
        except:
            pass

    update.message.reply_text("✅ تم الإرسال")
    return ConversationHandler.END

def cancel(update, context):
    update.message.reply_text("❌ تم الإلغاء", reply_markup=main_menu())
    return ConversationHandler.END

# ---------------- الرسائل ----------------
def handle_message(update, context):
    text = update.message.text

    if text == "📂 حساباتي":
        show_accounts(update, context)

    elif text == "💰 محفظتي":
        update.message.reply_text("💰 اختر عملية")

    elif text == "➕ إنشاء حساب":
        update.message.reply_text("👤 اكتب username:")
        return USERNAME

# ---------------- تشغيل ----------------
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(Filters.regex("^➕ إنشاء حساب$"), get_username),
        ],
        states={
            USERNAME: [MessageHandler(Filters.text & ~Filters.command, get_username)],
            PASSWORD: [MessageHandler(Filters.text & ~Filters.command, get_password)],
            AMOUNT: [MessageHandler(Filters.text & ~Filters.command, amount_handler)],
            CHANGE_PASSWORD: [MessageHandler(Filters.text & ~Filters.command, change_password_save)],
            ADMIN_BROADCAST: [MessageHandler(Filters.text & ~Filters.command, admin_broadcast_send)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("admin", admin_panel))
    dp.add_handler(conv_handler)
    dp.add_handler(CallbackQueryHandler(button))
    dp.add_handler(MessageHandler(Filters.text, handle_message))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
