import telebot
from telebot import types
import json
import os

TOKEN = "8689931840:AAH44pUtOgX6RGkg4NSF5-KoZDbOip8rBgo"
GROUP_ID = -1003727920702

bot = telebot.TeleBot(TOKEN)

managers_file = "managers.json"

if os.path.exists(managers_file):
    with open(managers_file, "r", encoding="utf-8") as f:
        managers = json.load(f)
else:
    managers = {}

user_data = {}
applications = {}


def save_managers():
    with open(managers_file, "w", encoding="utf-8") as f:
        json.dump(managers, f, ensure_ascii=False)


def main_menu():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("➕ Новая заявка"))
    return keyboard


@bot.message_handler(commands=['start'])
def start(message):
    chat_id = str(message.chat.id)

    if chat_id not in managers:
        user_data[chat_id] = {"step": "register"}
        bot.send_message(chat_id, "Введите ваше ФИО")
    else:
        bot.send_message(
            chat_id,
            f"Здравствуйте {managers[chat_id]}",
            reply_markup=main_menu()
        )


@bot.message_handler(content_types=['text', 'photo'])
def handler(message):

    chat_id = str(message.chat.id)

    # регистрация менеджера
    if chat_id in user_data and user_data[chat_id]["step"] == "register":
        managers[chat_id] = message.text
        save_managers()

        bot.send_message(
            chat_id,
            "Регистрация завершена",
            reply_markup=main_menu()
        )

        del user_data[chat_id]
        return

    # новая заявка
    if message.text == "➕ Новая заявка":
        user_data[chat_id] = {
            "step": "client_code",
            "photos": []
        }

        bot.send_message(chat_id, "Введите код клиента")
        return

    if chat_id not in user_data:
        return

    step = user_data[chat_id]["step"]

    if step == "client_code":

        user_data[chat_id]["client_code"] = message.text
        user_data[chat_id]["step"] = "photos"

        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(types.KeyboardButton("✅ Готово"))

        bot.send_message(
            chat_id,
            "Отправьте фото клиента (можно несколько)",
            reply_markup=keyboard
        )

    elif step == "photos":

        if message.photo:

            user_data[chat_id]["photos"].append(
                message.photo[-1].file_id
            )

            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.add(types.KeyboardButton("✅ Готово"))

            bot.send_message(
                chat_id,
                "Фото добавлено. Отправьте ещё или нажмите «✅ Готово»",
                reply_markup=keyboard
            )

        elif message.text == "✅ Готово":

            if len(user_data[chat_id]["photos"]) == 0:
                bot.send_message(chat_id, "Добавьте хотя бы одно фото")
                return

            user_data[chat_id]["step"] = "sum"
            bot.send_message(chat_id, "Введите сумму кредита")

    elif step == "sum":

        user_data[chat_id]["sum"] = message.text
        user_data[chat_id]["step"] = "goal"

        bot.send_message(chat_id, "Введите цель кредита")

    elif step == "goal":

        user_data[chat_id]["goal"] = message.text
        user_data[chat_id]["step"] = "note"

        bot.send_message(chat_id, "Введите примечание")

    elif step == "note":

        user_data[chat_id]["note"] = message.text
        manager_name = managers.get(chat_id)

        photos = user_data[chat_id]["photos"]

        media = []

        media.append(
            types.InputMediaPhoto(photos[0])
        )

        for p in photos[1:]:
            media.append(types.InputMediaPhoto(p))

        # отправляем альбом фото
        media_messages = bot.send_media_group(GROUP_ID, media)

        first_photo_id = media_messages[0].message_id

        text = f"""
📥 НОВАЯ ЗАЯВКА

👨‍💼 Менеджер: {manager_name}
🆔 Код клиента: {user_data[chat_id]['client_code']}
💰 Сумма: {user_data[chat_id]['sum']}
🎯 Цель: {user_data[chat_id]['goal']}
📝 Примечание: {user_data[chat_id]['note']}

Статус: ⏳ На рассмотрении
"""

        keyboard = types.InlineKeyboardMarkup()

        approve = types.InlineKeyboardButton(
            "✅ Одобрить",
            callback_data="approve"
        )

        reject = types.InlineKeyboardButton(
            "❌ Отказать",
            callback_data="reject"
        )

        keyboard.add(approve, reject)

        msg = bot.send_message(
            GROUP_ID,
            text,
            reply_to_message_id=first_photo_id,
            reply_markup=keyboard
        )

        applications[msg.message_id] = chat_id

        bot.send_message(
            chat_id,
            "✅ Заявка отправлена",
            reply_markup=main_menu()
        )

        del user_data[chat_id]


@bot.callback_query_handler(func=lambda call: True)
def callback(call):

    manager_chat = applications.get(call.message.message_id)

    if call.data == "approve":

        bot.edit_message_text(
            call.message.text + "\n\n✅ ЗАЯВКА ОДОБРЕНА",
            call.message.chat.id,
            call.message.message_id
        )

        if manager_chat:
            bot.send_message(
                manager_chat,
                "✅ Ваша заявка одобрена"
            )

    elif call.data == "reject":

        bot.edit_message_text(
            call.message.text + "\n\n❌ ЗАЯВКА ОТКЛОНЕНА",
            call.message.chat.id,
            call.message.message_id
        )

        if manager_chat:
            bot.send_message(
                manager_chat,
                "❌ Ваша заявка отклонена"
            )


bot.infinity_polling()