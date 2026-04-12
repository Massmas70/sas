# -*- coding: utf-8 -*-

import os
import psycopg2
from telegram import *
from telegram.ext import *

TOKEN = os.getenv("TOKEN")

# ---------------- الاتصال بقاعدة البيانات ----------------
conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cursor = conn.cursor()

# ---------------- إنشاء الجداول ----------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    wallet INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS accounts (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    username TEXT,
    password TEXT,
    balance INTEGER DEFAULT 0
)
""")

conn.commit()

# ---------------- القائمة ----------------
def main_menu():
    return ReplyKeyboardMarkup([
        ["📂 حساباتي", "➕ إنشاء حساب"],
        ["💳 تعبئة/سحب", "💰 محفظتي"]
    ], resize_keyboard=True)

# ---------------- start ----------------
def start(update, context):
    user_id = update.effective_user.id

    cursor.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
    user = cursor.fetchone()

    if not user:
        cursor.execute("INSERT INTO users (user_id) VALUES (%s)", (user_id,))
        conn.commit()

    update.message.reply_text("👋 أهلا بك", reply_markup=main_menu())

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

    update.message.reply_text("📂 حساباتك:", reply_markup=InlineKeyboardMarkup(keyboard))

# ---------------- الأزرار ----------------
def button(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    query.answer()

    if data.startswith("acc_"):
        acc_id = int(data.split("_")[1])

        cursor.execute("SELECT username, password, balance FROM accounts WHERE id=%s", (acc_id,))
        acc = cursor.fetchone()

        context.user_data["selected_account"] = acc_id

        keyboard = [
            [InlineKeyboardButton("❌ حذف", callback_data="delete")],
            [InlineKeyboardButton("🔑 تغيير كلمة السر", callback_data="change_pass")]
        ]

        query.edit_message_text(
            f"👤 {acc[0]}\n🔑 {acc[1]}\n💰 {acc[2]} ل.س",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "delete":
        acc_id = context.user_data["selected_account"]
        cursor.execute("DELETE FROM accounts WHERE id=%s", (acc_id,))
        conn.commit()
        query.edit_message_text("✅ تم حذف الحساب")

    elif data == "change_pass":
        context.user_data["step"] = "change_pass"
        query.message.reply_text("✏️ اكتب كلمة السر الجديدة:")

    elif data.startswith("select_"):
        acc_id = int(data.split("_")[1])
        context.user_data["selected_account"] = acc_id
        context.user_data["step"] = "amount"
        query.message.reply_text("💰 اكتب المبلغ:")

    elif data in ["deposit_acc", "withdraw_acc"]:
        acc_id = context.user_data["selected_account"]
        amount = context.user_data["amount"]

        if data == "deposit_acc":
            cursor.execute("SELECT wallet FROM users WHERE user_id=%s", (user_id,))
            wallet = cursor.fetchone()[0]

            if wallet >= amount:
                cursor.execute("UPDATE users SET wallet = wallet - %s WHERE user_id=%s", (amount, user_id))
                cursor.execute("UPDATE accounts SET balance = balance + %s WHERE id=%s", (amount, acc_id))
                conn.commit()
                query.message.reply_text("✅ تم التعبئة")
            else:
                query.message.reply_text("❌ الرصيد غير كافي")

        elif data == "withdraw_acc":
            cursor.execute("SELECT balance FROM accounts WHERE id=%s", (acc_id,))
            balance = cursor.fetchone()[0]

            if balance >= amount:
                cursor.execute("UPDATE accounts SET balance = balance - %s WHERE id=%s", (amount, acc_id))
                cursor.execute("UPDATE users SET wallet = wallet + %s WHERE user_id=%s", (amount, user_id))
                conn.commit()
                query.message.reply_text("✅ تم السحب")
            else:
                query.message.reply_text("❌ رصيد الحساب غير كافي")

# ---------------- الرسائل ----------------
def handle_message(update, context):
    user_id = update.effective_user.id
    text = update.message.text

    if text == "💰 محفظتي":
        cursor.execute("SELECT wallet FROM users WHERE user_id=%s", (user_id,))
        wallet = cursor.fetchone()[0]

        update.message.reply_text(f"💰 رصيدك: {wallet} ل.س")

    elif text == "📂 حساباتي":
        show_accounts(update, context)

    elif text == "➕ إنشاء حساب":
        context.user_data["step"] = "username"
        update.message.reply_text("👤 اكتب username:")

    elif context.user_data.get("step") == "username":
        context.user_data["username"] = text
        context.user_data["step"] = "password"
        update.message.reply_text("🔑 اكتب password:")

    elif context.user_data.get("step") == "password":
        cursor.execute(
            "INSERT INTO accounts (user_id, username, password) VALUES (%s, %s, %s)",
            (user_id, context.user_data["username"], text)
        )
        conn.commit()

        context.user_data["step"] = None
        update.message.reply_text("✅ تم إنشاء الحساب")

    elif text == "💳 تعبئة/سحب":
        cursor.execute("SELECT id, username FROM accounts WHERE user_id=%s", (user_id,))
        accounts = cursor.fetchall()

        keyboard = [
            [InlineKeyboardButton(acc[1], callback_data=f"select_{acc[0]}")]
            for acc in accounts
        ]

        update.message.reply_text("اختر الحساب:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif context.user_data.get("step") == "amount":
        try:
            context.user_data["amount"] = int(text)
        except:
            update.message.reply_text("❌ أدخل رقم صحيح")
            return

        context.user_data["step"] = None

        keyboard = [
            [InlineKeyboardButton("➕ تعبئة", callback_data="deposit_acc")],
            [InlineKeyboardButton("➖ سحب", callback_data="withdraw_acc")]
        ]

        update.message.reply_text("اختر العملية:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif context.user_data.get("step") == "change_pass":
        acc_id = context.user_data["selected_account"]

        cursor.execute("UPDATE accounts SET password=%s WHERE id=%s", (text, acc_id))
        conn.commit()

        context.user_data["step"] = None
        update.message.reply_text("✅ تم تغيير كلمة السر")

# ---------------- تشغيل ----------------
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text, handle_message))
    dp.add_handler(CallbackQueryHandler(button))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
