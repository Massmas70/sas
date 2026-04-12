# -*- coding: utf-8 -*-

import os
import psycopg2
from telegram import *
from telegram.ext import *

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

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

conn.commit()

# ---------------- القائمة الرئيسية ----------------
def main_menu():
    return ReplyKeyboardMarkup([
        ["📂 حساباتي", "➕ إنشاء حساب"],
        ["💳 تعبئة/سحب", "💰 محفظتي"],
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

    # عرض حساب
    if data.startswith("acc_"):
        acc_id = int(data.split("_")[1])

        cursor.execute("SELECT username, password, balance FROM accounts WHERE id=%s", (acc_id,))
        acc = cursor.fetchone()

        context.user_data["account_id"] = acc_id

        keyboard = [
            [InlineKeyboardButton("❌ حذف", callback_data="delete")],
            [InlineKeyboardButton("🔑 تغيير كلمة السر", callback_data="change_pass")]
        ]

        query.edit_message_text(
            f"👤 {acc[0]}\n🔑 {acc[1]}\n💰 {acc[2]} ل.س",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # حذف
    elif data == "delete":
        acc_id = context.user_data.get("account_id")

        cursor.execute("DELETE FROM accounts WHERE id=%s", (acc_id,))
        conn.commit()

        query.edit_message_text("✅ تم حذف الحساب")

    # تغيير كلمة السر
    elif data == "change_pass":
        context.user_data["step"] = "change_pass"
        query.message.reply_text("✏️ اكتب كلمة السر الجديدة:")

    # اختيار حساب للتحويل
    elif data.startswith("select_"):
        acc_id = int(data.split("_")[1])
        context.user_data["account_id"] = acc_id
        context.user_data["step"] = "amount_account"

        query.message.reply_text("💰 اكتب المبلغ:")

    # تعبئة/سحب من الحساب
    elif data in ["deposit_acc", "withdraw_acc"]:
        acc_id = context.user_data.get("account_id")
        amount = context.user_data.get("amount")

        # جلب الرصيد
        cursor.execute("SELECT wallet FROM users WHERE user_id=%s", (user_id,))
        wallet = cursor.fetchone()[0]

        cursor.execute("SELECT balance FROM accounts WHERE id=%s", (acc_id,))
        balance = cursor.fetchone()[0]

        if data == "deposit_acc":
            if wallet >= amount:
                cursor.execute("UPDATE users SET wallet=wallet-%s WHERE user_id=%s", (amount, user_id))
                cursor.execute("UPDATE accounts SET balance=balance+%s WHERE id=%s", (amount, acc_id))
                cursor.execute("INSERT INTO history (user_id, action) VALUES (%s, %s)",
                               (user_id, f"➕ {amount} إلى الحساب"))
                conn.commit()
                query.message.reply_text("✅ تم التعبئة")
            else:
                query.message.reply_text("❌ الرصيد غير كافي")

        elif data == "withdraw_acc":
            if balance >= amount:
                cursor.execute("UPDATE accounts SET balance=balance-%s WHERE id=%s", (amount, acc_id))
                cursor.execute("UPDATE users SET wallet=wallet+%s WHERE user_id=%s", (amount, user_id))
                cursor.execute("INSERT INTO history (user_id, action) VALUES (%s, %s)",
                               (user_id, f"➖ {amount} إلى المحفظة"))
                conn.commit()
                query.message.reply_text("✅ تم السحب")
            else:
                query.message.reply_text("❌ رصيد الحساب غير كافي")

    # المحفظة
    elif data == "deposit_wallet":
        context.user_data["step"] = "deposit_wallet"
        query.message.reply_text("💰 أدخل المبلغ:")

    elif data == "withdraw_wallet":
        context.user_data["step"] = "withdraw_wallet"
        query.message.reply_text("💰 أدخل المبلغ:")

    # السجل
    elif data == "history":
        cursor.execute("SELECT action FROM history WHERE user_id=%s ORDER BY id DESC LIMIT 10", (user_id,))
        logs = cursor.fetchall()

        msg = "\n".join([log[0] for log in logs]) if logs else "لا يوجد عمليات"
        query.message.reply_text(msg)

    # طرق الدفع
    elif data in ["syriatel", "sham"]:
        amount = context.user_data.get("amount")
        action = context.user_data.get("action")

        cursor.execute("SELECT wallet FROM users WHERE user_id=%s", (user_id,))
        wallet = cursor.fetchone()[0]

        if action == "deposit_wallet":
            cursor.execute("UPDATE users SET wallet=wallet+%s WHERE user_id=%s", (amount, user_id))
            cursor.execute("INSERT INTO history (user_id, action) VALUES (%s, %s)",
                           (user_id, f"➕ {amount} شحن"))
            conn.commit()
            query.message.reply_text("✅ تم الشحن")

        elif action == "withdraw_wallet":
            if wallet < amount:
                query.message.reply_text("❌ الرصيد غير كافي")
                return

            cursor.execute("UPDATE users SET wallet=wallet-%s WHERE user_id=%s", (amount, user_id))
            cursor.execute("INSERT INTO history (user_id, action) VALUES (%s, %s)",
                           (user_id, f"➖ {amount} سحب"))
            conn.commit()
            query.message.reply_text("✅ تم السحب")

# ---------------- الرسائل ----------------
def handle_message(update, context):
    user_id = update.effective_user.id
    text = update.message.text
    step = context.user_data.get("step")

    if text == "💰 محفظتي":
        cursor.execute("SELECT wallet FROM users WHERE user_id=%s", (user_id,))
        wallet = cursor.fetchone()[0]

        keyboard = [
            [InlineKeyboardButton("➕ تعبئة المحفظة", callback_data="deposit_wallet")],
            [InlineKeyboardButton("➖ سحب من المحفظة", callback_data="withdraw_wallet")],
            [InlineKeyboardButton("📊 العمليات", callback_data="history")]
        ]

        update.message.reply_text(f"💰 رصيدك: {wallet} ل.س",
                                  reply_markup=InlineKeyboardMarkup(keyboard))

    elif text == "📂 حساباتي":
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

    elif text == "💳 تعبئة/سحب":
        cursor.execute("SELECT id, username FROM accounts WHERE user_id=%s", (user_id,))
        accounts = cursor.fetchall()

        if not accounts:
            update.message.reply_text("❌ لا يوجد حسابات")
            return

        keyboard = [
            [InlineKeyboardButton(acc[1], callback_data=f"select_{acc[0]}")]
            for acc in accounts
        ]

        update.message.reply_text("اختر الحساب:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif step == "amount_account":
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

    elif step == "deposit_wallet":
        context.user_data["amount"] = int(text)
        context.user_data["action"] = "deposit_wallet"
        context.user_data["step"] = None

        keyboard = [
            [InlineKeyboardButton("📱 سيريتيل", callback_data="syriatel")],
            [InlineKeyboardButton("📱 شام", callback_data="sham")]
        ]

        update.message.reply_text("اختر:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif step == "withdraw_wallet":
        context.user_data["amount"] = int(text)
        context.user_data["action"] = "withdraw_wallet"
        context.user_data["step"] = None

        keyboard = [
            [InlineKeyboardButton("📱 سيريتيل", callback_data="syriatel")],
            [InlineKeyboardButton("📱 شام", callback_data="sham")]
        ]

        update.message.reply_text("اختر:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif step == "change_pass":
        acc_id = context.user_data.get("account_id")

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
