import asyncio
import logging
import json
import os
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton, 
                           InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto, InputMediaVideo, InputMediaAnimation)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Настройки бота
API_TOKEN = "7530716464:AAEEnqZLchL5GGrNYOAocqNpi8-8loaaSbY"  # Замени на свой токен
CHANNEL_USERNAME = "@CorteizProjects"  # Замени на username твоего канала
ADMIN_ID = 886103881  # Замени на свой Telegram ID
STICKER_ID = "CAACAgIAAxkBAAEMgApnrNqFHMQqHOPwDMetOA5iK3MXeQACJi4AAguccEj5Jpxf8oKEGDYE"  # Замени на ID нужного стикера
REVIEWS_FILE = "reviews.json"

# Инициализация бота
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Flask сервер для UptimeRobot
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот работает!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Список отзывов
reviews = []

# Загрузка отзывов из JSON
def load_reviews():
    global reviews
    if os.path.exists(REVIEWS_FILE):
        with open(REVIEWS_FILE, "r", encoding="utf-8") as f:
            reviews = json.load(f)

# Сохранение отзывов в JSON
def save_reviews():
    with open(REVIEWS_FILE, "w", encoding="utf-8") as f:
        json.dump(reviews, f, ensure_ascii=False, indent=4)

# Загрузка отзывов при старте
load_reviews()

# Состояния для FSM
class AddReviewState(StatesGroup):
    waiting_for_media = State()
    waiting_for_text = State()

# Основная клавиатура
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📄 Смотреть отзывы")]],
    resize_keyboard=True
)

# Клавиатура проверки подписки
check_subscription_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Проверка подписки", callback_data="check_subscription")]
    ]
)

async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in {"member", "administrator", "creator"}
    except Exception:
        return False

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    is_subscribed = await check_subscription(message.from_user.id)
    if not is_subscribed:
        await message.answer(
            "👋 Добро пожаловать! Подпишитесь на канал @CorteizProjects, чтобы использовать бота.",
            reply_markup=check_subscription_keyboard
        )
    else:
        await bot.send_sticker(message.chat.id, STICKER_ID)
        await message.answer("👋 Добро пожаловать! Нажмите кнопку ниже, чтобы посмотреть отзывы.", reply_markup=main_keyboard)

@dp.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery):
    is_subscribed = await check_subscription(callback.from_user.id)
    if is_subscribed:
        await callback.message.answer("✔️ Вы подписаны! Напишите /start для начала работы.")
    else:
        await callback.message.answer("❌ Вы не подписаны. Вступите в канал, чтобы продолжить.")
    await callback.answer()

@dp.message(F.text == "📄 Смотреть отзывы")
async def show_review(message: types.Message):
    if not reviews:
        await message.answer("❌ Отзывы пока отсутствуют.")
        return
    media_files, review_text = reviews[0]
    next_index = 1 % len(reviews)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton("Следующий", callback_data=f"show_review_{next_index}")]]
    )
    
    await bot.send_media_group(message.chat.id, media_files)
    await message.answer(review_text, reply_markup=keyboard)

@dp.callback_query(F.data.startswith("show_review_"))
async def show_next_review(callback: CallbackQuery):
    index = int(callback.data.split("_")[2])
    if not reviews:
        await callback.answer("❌ Отзывы пока отсутствуют.", show_alert=True)
        return
    index %= len(reviews)
    media_files, review_text = reviews[index]
    next_index = (index + 1) % len(reviews)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton("Следующий", callback_data=f"show_review_{next_index}")]]
    )
    
    await bot.send_media_group(callback.message.chat.id, media_files)
    await callback.message.answer(review_text, reply_markup=keyboard)

@dp.message(Command("add_review"))
async def add_review_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Вы не можете добавить отзыв.")
        return
    await message.answer("Отправьте фото, видео или гифки для отзыва (до 3 медиа).")
    await state.set_state(AddReviewState.waiting_for_media)

@dp.message(F.content_type.in_([types.ContentType.PHOTO, types.ContentType.VIDEO, types.ContentType.ANIMATION]), AddReviewState.waiting_for_media)
async def process_media(message: types.Message, state: FSMContext):
    data = await state.get_data()
    media_files = data.get("media_files", [])
    
    if message.photo:
        media_files.append({"type": "photo", "file_id": message.photo[-1].file_id})
    elif message.video:
        media_files.append({"type": "video", "file_id": message.video.file_id})
    elif message.animation:
        media_files.append({"type": "animation", "file_id": message.animation.file_id})

    if len(media_files) > 3:
        await message.answer("Максимум 3 медиа! Отправьте заново.")
        return

    await state.update_data(media_files=media_files)
    await message.answer("Теперь отправьте текст для отзыва.")
    await state.set_state(AddReviewState.waiting_for_text)

@dp.message(AddReviewState.waiting_for_text)
async def process_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    media_files = data.get("media_files", [])
    
    reviews.append((media_files, message.text))
    save_reviews()
    await message.answer("✔️ Отзыв добавлен!")
    await state.clear()

async def run_bot():
    keep_alive()
    while True:
        try:
            await dp.start_polling(bot, skip_updates=True)
        except Exception as e:
            logging.error(f"❌ Ошибка: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(run_bot())


