import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters import Command
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
import logging

API_TOKEN = "7530716464:AAEEnqZLchL5GGrNYOAocqNpi8-8loaaSbY"  # Замени на свой токен
CHANNEL_USERNAME = "@CorteizProjects"  # Замени на username твоего канала
ADMIN_ID = 886103881  # Замени на свой Telegram ID
STICKER_ID = "CAACAgIAAxkBAAEMgApnrNqFHMQqHOPwDMetOA5iK3MXeQACJi4AAguccEj5Jpxf8oKEGDYE"  # Замени на ID нужного стикера

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# Список отзывов
reviews = []

# Состояния для FSM (Finite State Machine)
class AddReviewState(StatesGroup):
    waiting_for_media = State()  # Ожидаем медиа (картинки, видео, гифки)
    waiting_for_text = State()  # Ожидаем текст для отзыва

# Основная клавиатура с кнопкой «📄 Смотреть отзывы»
main_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
main_keyboard.add(KeyboardButton("📄 Смотреть отзывы"))

# Клавиатура для проверки подписки
check_subscription_keyboard = InlineKeyboardMarkup().add(
    InlineKeyboardButton("Проверка подписки", callback_data="check_subscription")
)

async def check_subscription(user_id: int):
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False

@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    # Проверка подписки
    is_subscribed = await check_subscription(message.from_user.id)

    if not is_subscribed:
        # Если пользователь не подписан, отправляем сообщение и кнопку для проверки подписки
        await message.reply(
            "👋 Добро пожаловать! Пожалуйста, подпишитесь на наш канал, чтобы использовать бот.\n @CorteizProjects",
            reply_markup=check_subscription_keyboard
        )
    else:
        # Если подписан — продолжаем как обычно
        await bot.send_sticker(message.chat.id, STICKER_ID)
        await message.answer("👋 Добро пожаловать! Для просмотра отзывов нажмите на кнопку внизу 👇", reply_markup=main_keyboard)

@dp.callback_query_handler(lambda c: c.data == "check_subscription")
async def check_subscription_callback(callback: types.CallbackQuery):
    is_subscribed = await check_subscription(callback.from_user.id)
    
    if is_subscribed:
        await callback.message.answer("✔️ Вы подписаны на канал! Теперь вы можете использовать бота.")
        await callback.message.answer("Для начала работы напишите /start")
    else:
        await callback.message.answer("❌ Вы не подписаны на канал! Пожалуйста, вступите в канал, чтобы продолжить.")
    
    await callback.answer()

# Регистрируем остальные хендлеры для отзывов и медиа как раньше
@dp.message_handler(lambda message: message.text == "📄 Смотреть отзывы")
async def show_review(message: types.Message):
    if not reviews:
        await message.reply("❌ На данный момент отзывы отсутствуют. Ожидайте пока клиенты владельца добавят их!")
        return

    # Показываем первый отзыв
    media_files, review_text = reviews[0]
    next_index = 1 % len(reviews)

    keyboard = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("Следующий", callback_data=f"show_review_{next_index}")
    )

    # Отправляем медиа по одному
    for media in media_files:
        if isinstance(media, types.InputMediaPhoto):
            await bot.send_photo(message.chat.id, media.media)
        elif isinstance(media, types.InputMediaVideo):
            await bot.send_video(message.chat.id, media.media)
        elif isinstance(media, types.InputMediaAnimation):
            await bot.send_animation(message.chat.id, media.media)

    await bot.send_message(message.chat.id, review_text, reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("show_review_"))
async def show_next_review(callback: types.CallbackQuery):
    index = int(callback.data.split("_")[2])

    if not reviews:
        await callback.answer("❌ На данный момент отзывы отсутствуют. Ожидайте пока клиенты владельца добавят их!", show_alert=True)
        return

    index = index % len(reviews)  # Зацикливаемся по длине списка
    media_files, review_text = reviews[index]
    next_index = (index + 1) % len(reviews)

    keyboard = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("Следующий", callback_data=f"show_review_{next_index}")
    )

    # Отправляем медиа по одному
    for media in media_files:
        if isinstance(media, types.InputMediaPhoto):
            await bot.send_photo(callback.message.chat.id, media.media)
        elif isinstance(media, types.InputMediaVideo):
            await bot.send_video(callback.message.chat.id, media.media)
        elif isinstance(media, types.InputMediaAnimation):
            await bot.send_animation(callback.message.chat.id, media.media)

    await bot.send_message(callback.message.chat.id, review_text, reply_markup=keyboard)

# Добавление отзыва — начало процесса
@dp.message_handler(Command("add_review"))
async def add_review_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("К сожалению Вы не можете добавить отзыв сейчас! Попробуйте позже ⌚")
        return
    await message.reply("Отправьте фото, видео или гифки для отзыва (до 3 медиа).")
    await AddReviewState.waiting_for_media.set()

# Обработка медиа (картинки, видео, гифки)
@dp.message_handler(content_types=[types.ContentType.PHOTO, types.ContentType.VIDEO, types.ContentType.ANIMATION], state=AddReviewState.waiting_for_media)
async def process_media(message: types.Message, state: FSMContext):
    media_files = []
    # Если медиа - фото
    if message.content_type == types.ContentType.PHOTO:
        media_files.append(types.InputMediaPhoto(message.photo[-1].file_id))
    # Если медиа - видео
    elif message.content_type == types.ContentType.VIDEO:
        media_files.append(types.InputMediaVideo(message.video.file_id))
    # Если медиа - гифка
    elif message.content_type == types.ContentType.ANIMATION:
        media_files.append(types.InputMediaAnimation(message.animation.file_id))

    if len(media_files) < 3:  # Если медиа меньше 3
        await state.update_data(media_files=media_files)
        await message.reply("Отлично! Теперь отправьте текст для отзыва.")
        await AddReviewState.waiting_for_text.set()

    else:  # Если медиа более 3
        await message.reply("❗ Максимальное количество медиа — 3. Пожалуйста, отправьте 3 или меньше.")
    
# Обработка текста и завершение
@dp.message_handler(state=AddReviewState.waiting_for_text)
async def process_text(message: types.Message, state: FSMContext):
    text = message.text
    data = await state.get_data()
    media_files = data["media_files"]

    # Добавляем отзыв в список
    reviews.append((media_files, text))
    await message.reply("✔️ Ваш отзыв успешно был добавлен в бота!")

    await state.finish()

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())
