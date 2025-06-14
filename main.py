from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, create_engine, text
)
from sqlalchemy.orm import sessionmaker, declarative_base, Session
import os
import httpx


# ──────────────────  НАСТРОЙ MySQL  ──────────────────
database_url = f"mysql+pymysql://gen_user:{os.getenv('DB_PASS')}@{os.getenv('DB_HOST')}:3306/default_db"


engine = create_engine(database_url, echo=False)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


# ──────────────────  SQLAlchemy‑модели  ──────────────────
class Visit(Base):
    __tablename__ = "visits"
    id           = Column(Integer, primary_key=True)
    ts           = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"), index=True)
    ip           = Column(String(45))
    user_agent   = Column(Text)
    utm_source   = Column(String(100))
    utm_medium   = Column(String(100))
    utm_campaign = Column(String(100))
    utm_content  = Column(String(100))
    utm_term     = Column(String(100), index=True)
    utm_cpc      = Column(String(100))
    utm_url      = Column(String(600))
    content      = Column(String(100))
    country      = Column(String(100))
    city         = Column(String(100))
    language     = Column(String(100))
    platform     = Column(String(100))

class Postback(Base):
    __tablename__ = "postback"
    id = Column(Integer, primary_key=True)
    ts = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"), index=True)
    amount = Column(String(100))
    network = Column(String(100))
    click_id = Column(String(100))
    status = Column(String(100))



class Lead(Base):
    __tablename__ = "leads"
    id           = Column(Integer, primary_key=True)
    name         = Column(String(100))
    phone        = Column(String(50))
    utm_term     = Column(String(100), index=True)

class OneprofitClickback(Base):
    __tablename__ = "oneprofit_clickback"
    id           = Column(Integer, primary_key=True)
    amount       = Column(String(100))
    stream       = Column(String(100))
    subid1       = Column(String(100))
    subid2       = Column(String(100))
    subid3       = Column(String(100))
    subid4       = Column(String(100))
    subid5       = Column(String(100))
    order_id     = Column(String(100))


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
    utm_cpc: str = ""
    utm_url: str = ""
    content: str = ""
    country: str = ""
    city: str = ""
    language: str = ""
    platform: str = ""


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

# @app.get("/redirect/")
# async def redirect(request: Request, db: Session = Depends(get_db)):
#     db.query(Visit).select()
#     pass

# ─────────────────────  /api/visit  ──────────────────────
@app.post("/api/visit")
async def track_visit(data: UTM, request: Request, db: Session = Depends(get_db)):
    ip = request.headers.get("x-real-ip", "")
    ua = request.headers.get("user-agent", "")
    language = request.headers.get("accept-language", "")
    platform = request.headers.get("sec-ch-ua-platform", "")

    # Запрос к ipapi.co
    country = city = country_call_code = None
    # нужно добавить еще один сервис на всякий случай
    # try:
    #     async with httpx.AsyncClient() as client:
    #         geo_resp = await client.get(f"https://ipapi.co/{ip}/json/")
    #         geo_resp2 = None
    #         if geo_resp.status_code in (200, 201, 202, 203, 204):
    #             geo = geo_resp.json()
    #             country = geo.get("country")
    #             city = geo.get("city")
    #             country_call_code = geo.get("country_calling_code")
    #         else:
    #             pass
            
    # except Exception as e:
    #     print(f"Geo lookup failed: {e}")

    visit = Visit(
        ip=ip,
        user_agent=ua,
        utm_source=data.utm_source,
        utm_medium=data.utm_medium,
        utm_campaign=data.utm_campaign,
        utm_content=data.utm_content,
        utm_term=data.utm_term,
        utm_cpc=data.utm_cpc,
        utm_url=data.utm_url,
        content=data.content,
        country=country,
        city=city,
        language=language,
        platform=platform
    )
    db.add(visit)
    db.commit()
    return {"status": "ok", "id": visit.id}

@app.get('/api/postback')
async def postback(request: Request,
                   db: Session = Depends(get_db)):
    params = request.query_params
    amount = params.get('amount','')
    network = params.get('network','')
    click_id = params.get('click_id','')
    status = params.get('status','')
    postback = Postback(
        amount=amount,
        network=network,
        click_id=click_id,
        status=status
    )
    db.add(postback)
    db.commit()
    return {"status": "ok"}


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

@app.get("/api/oneprofit/clickback")
async def oneprofit_clickback(request: Request,
                              db: Session = Depends(get_db)):
    params = request.query_params
    amount = params.get('amount','')
    stream = params.get('stream','')
    subid1 = params.get('subid1','')
    subid2 = params.get('subid2','')
    subid3 = params.get('subid3','')
    subid4 = params.get('subid4','')
    subid5 = params.get('subid5','')
    order_id = params.get('order_id','')
    clickback = OneprofitClickback(
        amount=amount,
        stream=stream,
        subid1=subid1,
        subid2=subid2,
        subid3=subid3,
        subid4=subid4,
        subid5=subid5,
        order_id=order_id
    )
    db.add(clickback)
    db.commit()
    return {"status": f"ok, order id: {order_id}"}




# ────────────────────  health‑check  ─────────────────────
@app.get("/")
def index():
    return {"hello": "world"}
