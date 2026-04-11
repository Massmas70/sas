# -*- coding: utf-8 -*-

import os
import psycopg2
from telegram import *
from telegram.ext import *

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# ---------------- DB ----------------
def create_tables():
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

# ---------------- menu ----------------
def main_menu():
    return ReplyKeyboardMarkup([
        ["📂 حساباتي", "➕ إنشاء حساب"],
        ["💰 محفظتي"]
    ], resize_keyboard=True)

# ---------------- start ----------------
def start(update, context):
    user_id = update.effective_user.id

    cursor.execute("SELECT user_id FROM users WHERE user_id=%s", (user_id,))
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

    # ✅ فقط أسماء الحسابات
    keyboard = [
        [InlineKeyboardButton(acc[1], callback_data=f"acc_{acc[0]}")]
        for acc in accounts
    ]

    # ✅ معاملات الحسابات
    keyboard.append([InlineKeyboardButton("📊 معاملات الحسابات", callback_data="accounts_history")])

    # ✅ رجوع
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])

    update.message.reply_text("📂 حساباتك:", reply_markup=InlineKeyboardMarkup(keyboard))

# ---------------- الأزرار ----------------
def button(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    query.answer()

    if data == "back_main":
        query.message.reply_text("🔙 القائمة الرئيسية", reply_markup=main_menu())
        return

    # عرض حساب
    if data.startswith("acc_"):
        acc_id = int(data.split("_")[1])
        context.user_data["acc_id"] = acc_id

        cursor.execute("SELECT username, password, balance FROM accounts WHERE id=%s", (acc_id,))
        acc = cursor.fetchone()

        keyboard = [
            [InlineKeyboardButton("➕ تعبئة", callback_data="deposit_acc")],
            [InlineKeyboardButton("➖ سحب", callback_data="withdraw_acc")],
            [InlineKeyboardButton("🔑 تغيير كلمة السر", callback_data="change_pass")],
            [InlineKeyboardButton("❌ حذف الحساب", callback_data="delete")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]
        ]

        query.edit_message_text(
            f"👤 اسم المستخدم: {acc[0]}\n"
            f"🔑 كلمة السر: {acc[1]}\n"
            f"💰 الرصيد: {acc[2]}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "delete":
        cursor.execute("DELETE FROM accounts WHERE id=%s", (context.user_data["acc_id"],))
        conn.commit()
        query.message.reply_text("✅ تم حذف الحساب", reply_markup=main_menu())

    elif data == "change_pass":
        context.user_data["step"] = "change_pass"
        query.message.reply_text("✏️ اكتب كلمة السر الجديدة:")

    elif data == "deposit_acc":
        context.user_data["step"] = "deposit_acc_amount"
        query.message.reply_text("💰 أدخل المبلغ:")

    elif data == "withdraw_acc":
        context.user_data["step"] = "withdraw_acc_amount"
        query.message.reply_text("💰 أدخل المبلغ:")

    # معاملات الحسابات
    elif data == "accounts_history":
        cursor.execute("SELECT username, balance FROM accounts WHERE user_id=%s", (user_id,))
        rows = cursor.fetchall()

        msg = "📊 معاملات الحسابات:\n\n"
        for r in rows:
            msg += f"👤 {r[0]} | 💰 {r[1]}\n"

        query.message.reply_text(msg)

    # -------- المحفظة --------
    elif data == "deposit_wallet":
        context.user_data["action"] = "deposit"
        context.user_data["step"] = "amount_wallet"
        query.message.reply_text("💰 أدخل المبلغ:")

    elif data == "withdraw_wallet":
        context.user_data["action"] = "withdraw"
        context.user_data["step"] = "amount_wallet"
        query.message.reply_text("💰 أدخل المبلغ:")

# ---------------- الرسائل ----------------
def handle_message(update, context):
    user_id = update.effective_user.id
    text = update.message.text

    if text == "📂 حساباتي":
        show_accounts(update, context)

    elif text == "➕ إنشاء حساب":
        context.user_data["step"] = "username"
        update.message.reply_text("👤 اكتب username:")

    elif context.user_data.get("step") == "username":
        context.user_data["username"] = text
        context.user_data["step"] = "password"
        update.message.reply_text("🔑 اكتب password:")

    elif context.user_data.get("step") == "password":
        cursor.execute("INSERT INTO accounts (user_id, username, password) VALUES (%s,%s,%s)",
                       (user_id, context.user_data["username"], text))
        conn.commit()
        context.user_data.clear()
        update.message.reply_text("✅ تم إنشاء الحساب", reply_markup=main_menu())

    elif context.user_data.get("step") == "deposit_acc_amount":
        amount = int(text)
        acc_id = context.user_data["acc_id"]

        cursor.execute("UPDATE users SET wallet = wallet - %s WHERE user_id=%s", (amount, user_id))
        cursor.execute("UPDATE accounts SET balance = balance + %s WHERE id=%s", (amount, acc_id))
        conn.commit()

        context.user_data.clear()
        update.message.reply_text("✅ تم التعبئة", reply_markup=main_menu())

    elif context.user_data.get("step") == "withdraw_acc_amount":
        amount = int(text)
        acc_id = context.user_data["acc_id"]

        cursor.execute("UPDATE accounts SET balance = balance - %s WHERE id=%s", (amount, acc_id))
        cursor.execute("UPDATE users SET wallet = wallet + %s WHERE user_id=%s", (amount, user_id))
        conn.commit()

        context.user_data.clear()
        update.message.reply_text("✅ تم السحب", reply_markup=main_menu())

    elif context.user_data.get("step") == "change_pass":
        cursor.execute("UPDATE accounts SET password=%s WHERE id=%s",
                       (text, context.user_data["acc_id"]))
        conn.commit()
        context.user_data.clear()
        update.message.reply_text("✅ تم تغيير كلمة السر", reply_markup=main_menu())

# ---------------- run ----------------
def main():
    create_tables()

    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text, handle_message))
    dp.add_handler(CallbackQueryHandler(button))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
