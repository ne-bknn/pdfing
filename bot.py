from utils import convert_to_pdf, save_document
import io
import asyncio
from aiogram import Bot, Dispatcher, executor, types, filters
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher.filters.state import State, StatesGroup
import logging
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import InputFile
from aiogram import types
import aiogram
from operator import itemgetter
from aiogram.contrib.middlewares.logging import LoggingMiddleware
import os

TOKEN = os.getenv("PDFING_TOKEN")
if TOKEN is None:
    raise Exception("No bot token is provided!")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
dp.middleware.setup(LoggingMiddleware())

class CreatePDF(StatesGroup):
    getting_pictures = State()
    getting_name = State()

@dp.message_handler(commands=['start', 'help'], state='*')
async def start(message: types.Message, state: FSMContext):
    await state.finish()
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton("Создать", callback_data="create"))
    await message.answer("Я помогу тебе сконвертировать твои картинки в pdf-файл. Нажми на кнопку ниже или отправь /create, дальше разберемя", reply_markup=keyboard)

@dp.message_handler(commands=['create'], state='*')
async def create(message: types.Message, state: FSMContext):
    await state.finish()
    await CreatePDF.getting_pictures.set()
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton("Отмена", callback_data="cancel"))
    await message.answer("Присылай картинки", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data and c.data == "create", state="*")
async def create_button(callback_query: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await bot.answer_callback_query(callback_query.id)
    await CreatePDF.getting_pictures.set()
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton("Отмена", callback_data="cancel"))
    await callback_query.message.answer("Присылай картинки", reply_markup=keyboard)


@dp.message_handler(content_types=["photo"], state=CreatePDF.getting_pictures)
async def get_images(message: types.Message, state: FSMContext):
    photo = await message.photo[-1].download(destination=io.BytesIO()) 
    try:
        photos = (await state.get_data())["photos"]
    except KeyError:
        await state.update_data(photos=[(message.message_id, photo)])
        photos = (await state.get_data())["photos"]
    else:
        photos.append((message.message_id, photo,))
        await state.update_data(photos=photos)

    n_photos = len(photos)

    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton("Отмена", callback_data="cancel"))
    keyboard.add(InlineKeyboardButton("Конвертировать", callback_data="convert"))

    new_message_to_delete = await message.answer(f"Получил! У меня есть {n_photos} фотографий.", reply_markup=keyboard)
    try:
        messages_to_delete = (await state.get_data())["mtd"]
    except KeyError:
        await state.update_data(mtd=[])
        messages_to_delete = (await state.get_data())["mtd"]
    else:
        for m in messages_to_delete:
            try:
                await m.delete()
            except aiogram.utils.exceptions.MessageToDeleteNotFound:
                pass

    messages_to_delete.append(new_message_to_delete)
    await state.update_data(mtd=messages_to_delete)

@dp.callback_query_handler(lambda c: c.data and c.data == "convert", state=CreatePDF.getting_pictures)
async def get_name(callback_query: types.CallbackQuery, state=FSMContext):
    await bot.answer_callback_query(callback_query.id)
    await CreatePDF.getting_name.set()
    await callback_query.message.answer("Как назвать файл?") 

@dp.message_handler(state=CreatePDF.getting_name)
async def create_file(message: types.Message, state: FSMContext):
    photos = (await state.get_data())["photos"]
    sorted_photos = [photo[1] for photo in sorted(photos, key=itemgetter(0))]
    pdf = await convert_to_pdf(sorted_photos)
    filename = message.text if message.text.endswith(".pdf") else message.text+".pdf"

    asyncio.create_task(save_document(pdf, filename))

    document = InputFile(pdf, filename=filename)

    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton("Создать еще", callback_data="create"))

    await state.finish()

    await message.answer_document(document=document, reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data and c.data == "cancel", state="*")
async def cancel_converting(callback_query: types.CallbackQuery, state=FSMContext):
    await bot.answer_callback_query(callback_query.id)
    await state.finish()

    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton("Начать", callback_data="create"))

    await callback_query.message.answer("Сбросил состояние! Отправь /create или нажми на кнопку чтобы начать заново", reply_markup=keyboard)

@dp.message_handler(content_types=types.ContentTypes.ANY, state="*")
async def default(message: types.Message):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton("Создать", callback_data="create"))

    await message.answer("Я тебя не понял((( Возможно, ты хотел нажать /create или на кнопку и прислать картинки?", reply_markup=keyboard)

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
