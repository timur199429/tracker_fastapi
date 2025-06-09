from fastapi import FastAPI, Request
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
    utm_source: str = ""
    utm_medium: str = ""
    utm_campaign: str = ""
    utm_content: str = ""
    utm_term: str = ""

# загрушка
@app.get("/")
def index():
    return {"hello": "world"}

# 📬 Обработчик POST-запроса
@app.post("/api/contact")
async def submit_contact(form: ContactForm, request: Request):
    user_agent = request.headers.get("user-agent")
    print(f"Заявка от: {form.name}, {form.phone}")
    print("UTM:", form.utm_source, form.utm_medium, form.utm_campaign)
    print("User-Agent:", user_agent)
    return {"status": "ok"}

# if __name__ == '__main__':
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)