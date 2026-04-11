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

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        type TEXT,
        amount INTEGER,
        method TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()

# ---------------- menu ----------------
def main_menu():
    return ReplyKeyboardMarkup([
        ["📂 حساباتي", "➕ إنشاء حساب"],
        ["💳 تعبئة/سحب", "💰 محفظتي"]
    ], resize_keyboard=True)

# ---------------- start ----------------
def start(update, context):
    user_id = update.effective_user.id

    cursor.execute("SELECT user_id FROM users WHERE user_id=%s", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id) VALUES (%s)", (user_id,))
        conn.commit()

    update.message.reply_text("👋 أهلا بك", reply_markup=main_menu())

# ---------------- accounts ----------------
def show_accounts(update, context):
    user_id = update.effective_user.id

    cursor.execute("SELECT id, username FROM accounts WHERE user_id=%s", (user_id,))
    accounts = cursor.fetchall()

    if not accounts:
        update.message.reply_text("❌ لا يوجد حسابات", reply_markup=main_menu())
        return

    keyboard = [[InlineKeyboardButton(acc[1], callback_data=f"acc_{acc[0]}")] for acc in accounts]
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])

    update.message.reply_text("📂 حساباتك:", reply_markup=InlineKeyboardMarkup(keyboard))

# ---------------- buttons ----------------
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
            [InlineKeyboardButton("❌ حذف", callback_data="delete")],
            [InlineKeyboardButton("🔑 تغيير كلمة السر", callback_data="change_pass")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]
        ]

        query.edit_message_text(
            f"👤 {acc[0]}\n🔑 {acc[1]}\n💰 {acc[2]} ل.س",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "delete":
        cursor.execute("DELETE FROM accounts WHERE id=%s", (context.user_data["acc_id"],))
        conn.commit()
        query.message.reply_text("✅ تم حذف الحساب", reply_markup=main_menu())

    elif data == "change_pass":
        context.user_data["step"] = "change_pass"
        query.message.reply_text("✏️ اكتب كلمة السر الجديدة:")

    # اختيار حساب للتعبئة/السحب
    elif data.startswith("select_"):
        acc_id = int(data.split("_")[1])
        context.user_data["acc_id"] = acc_id
        context.user_data["step"] = "amount_account"
        query.message.reply_text("💰 أدخل المبلغ:")

    # تنفيذ تعبئة/سحب حساب
    elif data in ["deposit_acc", "withdraw_acc"]:
        acc_id = context.user_data.get("acc_id")
        amount = context.user_data.get("amount")

        if not acc_id or not amount:
            query.message.reply_text("❌ خطأ، أعد المحاولة", reply_markup=main_menu())
            return

        if data == "deposit_acc":
            cursor.execute("SELECT wallet FROM users WHERE user_id=%s", (user_id,))
            wallet = cursor.fetchone()[0]

            if wallet >= amount:
                cursor.execute("UPDATE users SET wallet = wallet - %s WHERE user_id=%s", (amount, user_id))
                cursor.execute("UPDATE accounts SET balance = balance + %s WHERE id=%s", (amount, acc_id))
                conn.commit()
                query.message.reply_text("✅ تم التعبئة", reply_markup=main_menu())
            else:
                query.message.reply_text("❌ الرصيد غير كافي", reply_markup=main_menu())

        else:
            cursor.execute("SELECT balance FROM accounts WHERE id=%s", (acc_id,))
            balance = cursor.fetchone()[0]

            if balance >= amount:
                cursor.execute("UPDATE accounts SET balance = balance - %s WHERE id=%s", (amount, acc_id))
                cursor.execute("UPDATE users SET wallet = wallet + %s WHERE user_id=%s", (amount, user_id))
                conn.commit()
                query.message.reply_text("✅ تم السحب", reply_markup=main_menu())
            else:
                query.message.reply_text("❌ رصيد الحساب غير كافي", reply_markup=main_menu())

        context.user_data.clear()

    # -------- المحفظة --------
    elif data == "deposit_wallet":
        context.user_data["action"] = "deposit"
        context.user_data["step"] = "amount_wallet"
        query.message.reply_text("💰 أدخل المبلغ:")

    elif data == "withdraw_wallet":
        context.user_data["action"] = "withdraw"
        context.user_data["step"] = "amount_wallet"
        query.message.reply_text("💰 أدخل المبلغ:")

    elif data == "history":
        cursor.execute("SELECT type, amount, method FROM transactions WHERE user_id=%s ORDER BY id DESC LIMIT 10", (user_id,))
        rows = cursor.fetchall()

        if not rows:
            query.message.reply_text("❌ لا يوجد عمليات", reply_markup=main_menu())
            return

        msg = "\n".join([f"{r[0]} | {r[1]} | {r[2]}" for r in rows])
        query.message.reply_text(msg, reply_markup=main_menu())

    elif data in ["syriatel", "sham"]:
        amount = context.user_data.get("amount")
        action = context.user_data.get("action")
        method = "سيريتيل كاش" if data == "syriatel" else "شام كاش"

        if not amount or not action:
            query.message.reply_text("❌ خطأ", reply_markup=main_menu())
            return

        if action == "deposit":
            cursor.execute("UPDATE users SET wallet = wallet + %s WHERE user_id=%s", (amount, user_id))
            cursor.execute("INSERT INTO transactions (user_id, type, amount, method) VALUES (%s,%s,%s,%s)", (user_id,"➕ تعبئة",amount,method))
            conn.commit()
            query.message.reply_text("✅ تم الشحن", reply_markup=main_menu())

        elif action == "withdraw":
            cursor.execute("SELECT wallet FROM users WHERE user_id=%s", (user_id,))
            wallet = cursor.fetchone()[0]

            if wallet < amount:
                query.message.reply_text("❌ الرصيد غير كافي", reply_markup=main_menu())
                return

            cursor.execute("UPDATE users SET wallet = wallet - %s WHERE user_id=%s", (amount, user_id))
            cursor.execute("INSERT INTO transactions (user_id, type, amount, method) VALUES (%s,%s,%s,%s)", (user_id,"➖ سحب",amount,method))
            conn.commit()
            query.message.reply_text("✅ تم السحب", reply_markup=main_menu())

        context.user_data.clear()

# ---------------- messages ----------------
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
        cursor.execute("INSERT INTO accounts (user_id, username, password) VALUES (%s,%s,%s)", (user_id,context.user_data["username"],text))
        conn.commit()
        context.user_data.clear()
        update.message.reply_text("✅ تم إنشاء الحساب", reply_markup=main_menu())

    elif text == "💳 تعبئة/سحب":
        cursor.execute("SELECT id, username FROM accounts WHERE user_id=%s", (user_id,))
        accounts = cursor.fetchall()

        if not accounts:
            update.message.reply_text("❌ لا يوجد حسابات", reply_markup=main_menu())
            return

        keyboard = [[InlineKeyboardButton(acc[1], callback_data=f"select_{acc[0]}")] for acc in accounts]
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])

        update.message.reply_text("اختر الحساب:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif context.user_data.get("step") == "amount_account":
        try:
            context.user_data["amount"] = int(text)
        except:
            update.message.reply_text("❌ أدخل رقم صحيح")
            return

        context.user_data["step"] = None

        keyboard = [
            [InlineKeyboardButton("➕ تعبئة", callback_data="deposit_acc")],
            [InlineKeyboardButton("➖ سحب", callback_data="withdraw_acc")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]
        ]

        update.message.reply_text("اختر العملية:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif text == "💰 محفظتي":
        cursor.execute("SELECT wallet FROM users WHERE user_id=%s", (user_id,))
        wallet = cursor.fetchone()[0]

        keyboard = [
            [InlineKeyboardButton("➕ تعبئة المحفظة", callback_data="deposit_wallet")],
            [InlineKeyboardButton("➖ سحب من المحفظة", callback_data="withdraw_wallet")],
            [InlineKeyboardButton("📊 العمليات", callback_data="history")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]
        ]

        update.message.reply_text(f"💰 رصيدك: {wallet}", reply_markup=InlineKeyboardMarkup(keyboard))

    elif context.user_data.get("step") == "amount_wallet":
        try:
            context.user_data["amount"] = int(text)
        except:
            update.message.reply_text("❌ أدخل رقم صحيح")
            return

        context.user_data["step"] = None

        keyboard = [
            [InlineKeyboardButton("📱 سيريتيل كاش", callback_data="syriatel")],
            [InlineKeyboardButton("📱 شام كاش", callback_data="sham")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]
        ]

        update.message.reply_text("اختر الطريقة:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif context.user_data.get("step") == "change_pass":
        cursor.execute("UPDATE accounts SET password=%s WHERE id=%s", (text, context.user_data["acc_id"]))
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
