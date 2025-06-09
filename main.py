from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# ✅ Разрешаем запросы с вашего фронтенда (например, с S3)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Лучше указать конкретный домен, например: ["https://your-s3-site.amazonaws.com"]
    allow_methods=["POST"],
    allow_headers=["*"],
)

# 📦 Модель входных данных
class ContactForm(BaseModel):
    name: str
    phone: str

# загрушка
@app.get("/")
def index():
    return {"hello": "world"}

# 📬 Обработчик POST-запроса
@app.post("/api/contact")
async def submit_contact(form: ContactForm):
    # 🔧 Тут можно сохранить в базу, логировать, отправить письмо и т.д.
    print(f"Получена заявка: имя = {form.name}, телефон = {form.phone}")

    return {"status": "ok", "message": "Контакт получен"}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)