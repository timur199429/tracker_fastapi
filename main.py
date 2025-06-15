from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, create_engine, text
)
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_500_INTERNAL_SERVER_ERROR
import os
import httpx
import asyncio


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

class Clickback(Base):
    __tablename__ = "clickback"
    id = Column(Integer, primary_key=True)
    ts = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"), index=True)
    amount = Column(String(100))
    network = Column(String(100))
    click_id = Column(String(100))
    teaser_id = Column(String(100))
    campaign_id = Column(String(100))
    site_id = Column(String(100))
    source_id = Column(String(100))



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

@app.get("/redirect/")
async def redirect(request: Request, db: Session = Depends(get_db)):
    utm_content = request.query_params.get('utm_content')
    utm_term = request.query_params.get('utm_term')

    url = f'https://eolnm.bestaffaiirs.net/?utm_source=da57dc555e50572d&ban=push&j1=1&s1=15344&s2=2135046&s3={utm_content}&s5={utm_term}&click_id={utm_term}'
    utms = UTM(**request.query_params)
    asyncio.create_task(track_visit(utms, request, db))
    return RedirectResponse(url)

# ─────────────────────  /api/visit  ──────────────────────
@app.post("/api/visit")
async def track_visit(data: UTM, request: Request, db: Session = Depends(get_db)):
    ip = request.headers.get("x-real-ip", "")
    ua = request.headers.get("user-agent", "")
    language = request.headers.get("accept-language", "")
    platform = request.headers.get("sec-ch-ua-platform", "")


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

@app.get('/api/clickback')
async def postback(request: Request, db: Session = Depends(get_db)):
    params = request.query_params
    amount = params.get('amount')
    network = params.get('network')
    click_id = params.get('click_id')
    teaser_id = params.get('teaser_id')
    site_id = params.get('site_id')
    source_id = params.get('source_id')
    campaign_id = params.get('campaign_id')

    try:
        clickback = Clickback(
            amount=amount,
            network=network,
            click_id=click_id,
            teaser_id=teaser_id,
            campaign_id=campaign_id,
            site_id=site_id,
            source_id=source_id
        )
        db.add(clickback)
        db.commit()
        return {"status": "ok"}

    except Exception as e:
        # Можно логировать ошибку
        # logger.error(f"Failed to process clickback: {e}")
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Server error")


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