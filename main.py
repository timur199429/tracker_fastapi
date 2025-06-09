from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, create_engine
)
from sqlalchemy.orm import sessionmaker, declarative_base, Session
import datetime as dt
import os

# ──────────────────  НАСТРОЙ MySQL  ──────────────────
DB_URL = f"mysql+pymysql://gen_user:{os.getenv('DB_PASS')}@{os.getenv('DB_HOST')}/default_db"


engine = create_engine(DB_URL, pool_recycle=280, echo=False)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


# ──────────────────  SQLAlchemy‑модели  ──────────────────
class Visit(Base):
    __tablename__ = "visits"
    id           = Column(Integer, primary_key=True)
    ts           = Column(DateTime, default=dt.datetime.now(tz=dt.timezone(dt.timedelta(hours=3))), index=True)
    ip           = Column(String(45))
    user_agent   = Column(Text)
    utm_source   = Column(String(100))
    utm_medium   = Column(String(100))
    utm_campaign = Column(String(100))
    utm_content  = Column(String(100))
    utm_term     = Column(String(100))


class Lead(Base):
    __tablename__ = "leads"
    id           = Column(Integer, primary_key=True)
    name         = Column(String(100))
    phone        = Column(String(50))
    utm_term     = Column(String(100))



# ──────────────  создаём таблицы, если их нет  ─────────────
Base.metadata.create_all(bind=engine)


# ───────────────────  FastAPI‑приложение  ──────────────────
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],              # желательно указать точный домен S3
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


# ────────────────  Pydantic‑схемы входа  ────────────────
class UTM(BaseModel):
    utm_source: str = ""
    utm_medium: str = ""
    utm_campaign: str = ""
    utm_content: str = ""
    utm_term: str = ""


class ContactForm(UTM):
    name: str
    phone: str


# ────────────────  DEP: сессия БД на запрос  ─────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─────────────────────  /api/visit  ──────────────────────
@app.post("/api/visit")
async def track_visit(data: UTM, request: Request, db: Session = Depends(get_db)):
    # IP: учитываем прокси / CDN
    ip = request.headers.get("x-real-ip", "")
    ua = request.headers.get("user-agent", "")

    visit = Visit(
        ip=ip,
        user_agent=ua,
        utm_source=data.utm_source,
        utm_medium=data.utm_medium,
        utm_campaign=data.utm_campaign,
        utm_content=data.utm_content,
        utm_term=data.utm_term,
    )
    db.add(visit)
    db.commit()
    return {"status": "ok", "id": visit.id}


# ────────────────────  /api/contact  ─────────────────────
@app.post("/api/lead")
async def submit_contact(form: ContactForm,
                         db: Session = Depends(get_db)):
    lead = Lead(
        name=form.name,
        phone=form.phone,
        utm_term=form.utm_term,
    )
    db.add(lead)
    db.commit()
    return {"status": "ok", "id": lead.id}


# ────────────────────  health‑check  ─────────────────────
@app.get("/")
def index():
    return {"hello": "world"}

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)