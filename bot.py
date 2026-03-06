import telebot
from telebot import types
import json
import os

TOKEN = "8689931840:AAH44pUtOgX6RGkg4NSF5-KoZDbOip8rBgo"
GROUP_ID = -1003727920702

bot = telebot.TeleBot(TOKEN)

# --- хранилища ---
managers_file = "managers.json"
if os.path.exists(managers_file):
    with open(managers_file, "r", encoding="utf-8") as f:
        managers = json.load(f)
else:
    managers = {}

user_data = {}
applications = {}
pending_reviews = {}

# --- сервисные функции ---
def save_managers():
    with open(managers_file, "w", encoding="utf-8") as f:
        json.dump(managers, f, ensure_ascii=False)

def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("➕ Новая заявка"))
    return kb

def photos_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("✅ Готово"))
    return kb

# --- старт / регистрация менеджера ---
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = str(message.chat.id)

    if chat_id not in managers:
        user_data[chat_id] = {"step": "register_name"}
        bot.send_message(chat_id, "Введите ваше ФИО менеджера:")
        return

    bot.send_message(chat_id, f"Здравствуйте, {managers[chat_id]['name']}", reply_markup=main_menu())

@bot.message_handler(content_types=['text','photo'])
def handler(message):
    chat_id = str(message.chat.id)

    # --- регистрация: ФИО ---
    if chat_id in user_data and user_data[chat_id]["step"] == "register_name":
        user_data[chat_id]["name"] = message.text
        user_data[chat_id]["step"] = "register_region"
        bot.send_message(chat_id, "Введите район:")
        return

    # --- регистрация: район ---
    if chat_id in user_data and user_data[chat_id]["step"] == "register_region":
        managers[chat_id] = {
            "name": user_data[chat_id]["name"],
            "region": message.text
        }
        save_managers()
        del user_data[chat_id]

        bot.send_message(chat_id, "Регистрация завершена", reply_markup=main_menu())
        return

    # --- новая заявка ---
    if message.text == "➕ Новая заявка":
        user_data[chat_id] = {"step":"client_code","photos":[]}
        bot.send_message(chat_id,"Введите код клиента")
        return

    if chat_id not in user_data:
        return

    step = user_data[chat_id]["step"]

    # --- код клиента ---
    if step == "client_code":
        user_data[chat_id]["client_code"] = message.text
        user_data[chat_id]["step"] = "client_name"
        bot.send_message(chat_id,"Введите ФИО клиента")
        return

    # --- ФИО клиента ---
    if step == "client_name":
        user_data[chat_id]["client_name"] = message.text
        user_data[chat_id]["step"] = "photos"
        bot.send_message(chat_id,"Отправьте фото клиента (можно несколько)", reply_markup=photos_keyboard())
        return

    # --- фото клиента ---
    if step == "photos":

        if message.photo:
            user_data[chat_id]["photos"].append(message.photo[-1].file_id)
            bot.send_message(chat_id,"Фото добавлено. Можно отправить ещё или нажать «Готово»", reply_markup=photos_keyboard())
            return

        if message.text == "✅ Готово":

            if len(user_data[chat_id]["photos"]) == 0:
                bot.send_message(chat_id,"Добавьте хотя бы одно фото")
                return

            user_data[chat_id]["step"] = "sum"
            bot.send_message(chat_id,"Введите сумму кредита")
            return

    # --- сумма ---
    if step == "sum":
        user_data[chat_id]["sum"] = message.text
        user_data[chat_id]["step"] = "goal"
        bot.send_message(chat_id,"Введите цель кредита")
        return

    # --- цель ---
    if step == "goal":
        user_data[chat_id]["goal"] = message.text
        user_data[chat_id]["step"] = "note"
        bot.send_message(chat_id,"Введите примечание")
        return

    # --- примечание ---
    if step == "note":

        user_data[chat_id]["note"] = message.text
        manager = managers.get(chat_id)

        photos = user_data[chat_id]["photos"]

        media = []
        media.append(types.InputMediaPhoto(photos[0]))
        for p in photos[1:]:
            media.append(types.InputMediaPhoto(p))

        # отправляем фото альбомом
        media_messages = bot.send_media_group(GROUP_ID, media)
        first_photo_id = media_messages[0].message_id

        text = f"""
📥 НОВАЯ ЗАЯВКА

👨‍💼 Менеджер: {manager['name']}
📍 Район: {manager['region']}

🆔 Код клиента: {user_data[chat_id]['client_code']}
👤 ФИО клиента: {user_data[chat_id]['client_name']}

💰 Сумма: {user_data[chat_id]['sum']}
🎯 Цель: {user_data[chat_id]['goal']}
📝 Примечание: {user_data[chat_id]['note']}

Статус: ⏳ На рассмотрении
"""

        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton("✅ Одобрить", callback_data="approve"),
            types.InlineKeyboardButton("❌ Отказать", callback_data="reject")
        )

        msg = bot.send_message(
            GROUP_ID,
            text,
            reply_to_message_id=first_photo_id,
            reply_markup=keyboard
        )

        applications[msg.message_id] = chat_id

        bot.send_message(chat_id,"✅ Заявка отправлена",reply_markup=main_menu())

        del user_data[chat_id]

# --- кнопки одобрить / отказать ---
@bot.callback_query_handler(func=lambda call: call.data in ["approve","reject"])
def review(call):

    pending_reviews[call.from_user.id] = {
        "action": call.data,
        "message_id": call.message.message_id,
        "chat_id": call.message.chat.id
    }

    bot.send_message(call.from_user.id,"Введите комментарий")

# --- комментарий админа ---
@bot.message_handler(func=lambda m: m.from_user.id in pending_reviews)
def handle_comment(message):

    review = pending_reviews[message.from_user.id]

    action = review["action"]
    comment = message.text

    status = "✅ ЗАЯВКА ОДОБРЕНА" if action=="approve" else "❌ ЗАЯВКА ОТКЛОНЕНА"

    text = f"""
{status}

💬 Комментарий:
{comment}
"""

    bot.send_message(
        review["chat_id"],
        text,
        reply_to_message_id=review["message_id"]
    )

    manager_chat = applications.get(review["message_id"])

    if manager_chat:
        bot.send_message(manager_chat,text)

    del pending_reviews[message.from_user.id]

bot.infinity_polling()
