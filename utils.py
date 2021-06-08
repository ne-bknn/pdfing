import img2pdf
import io
import asyncio
from concurrent.futures import ProcessPoolExecutor
from functools import partial
import hashlib

_executor = ProcessPoolExecutor(6)

def _convert_to_pdf(images):
    result_pdf = io.BytesIO()
    img2pdf.convert(images, outputstream=result_pdf)
    result_pdf.seek(0)
    return result_pdf

async def in_thread(func):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, func)

async def convert_to_pdf(images):
    result = await asyncio.gather(in_thread(partial(_convert_to_pdf, images)))
    return result[0]

def _save_document(data):
    pdf, name = data
    chars = []
    for c in name:
        if c == "/" or c == "\\" or c == ".":
            continue
        else:
            chars.append(c)
    name = "".join(chars)
    pdf.seek(0)
    h = hashlib.md5(pdf.read()).hexdigest()
    name = h+"_"+name
    pdf.seek(0)
    with open("pdfs/"+name, "wb") as f:
        f.write(pdf.read())

async def save_document(pdf, name):
    await asyncio.gather(in_thread(partial(_save_document, (pdf, name))))
