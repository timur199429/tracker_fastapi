import json
import random
import time
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, create_engine, func, select, text
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
    site_id      = Column(String(100))
    campaign_id  = Column(String(100))
    teaser_id    = Column(String(100))
    click_id     = Column(String(100), index=True)
    cpc          = Column(String(100))
    url          = Column(String(600))
    content      = Column(String(100))
    language     = Column(String(100))
    platform     = Column(String(100))
    news_id      = Column(String(100))

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

class Urls(Base):
    __tablename__ = "urls"
    id = Column(Integer, primary_key=True)
    url = Column(String(1000))
    domain = Column(String(200))
    category = Column(String(100))
    network = Column(String(100))
    geo = Column(String(100))



class Lead(Base):
    __tablename__ = "leads"
    id           = Column(Integer, primary_key=True)
    name         = Column(String(100))
    phone        = Column(String(50))
    utm_term     = Column(String(100), index=True)



# ──────────────  создаём таблицы, если их нет  ─────────────
Base.metadata.create_all(bind=engine)


# ───────────────────  FastAPI‑приложение  ──────────────────
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],              # желательно указать точный домен S3
    allow_methods=["*"],
    allow_credentials=True,
    allow_headers=["*"],
)


# ────────────────  Pydantic‑схемы входа  ────────────────
class UTM(BaseModel):
    utm_source: str = ""
    site_id: str = ""
    campaign_id: str = ""
    teaser_id: str = ""
    click_id: str = ""
    cpc: str = ""
    url: str = ""
    content: str = ""
    language: str = ""
    platform: str = ""
    news_id: str = ""


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


url_cache = {}
CACHE_TTL = 120  # секунды

def get_cached_urls(category: str, db: Session, ttl: int = CACHE_TTL):
    now = time.time()
    if category not in url_cache or now - url_cache[category]['last_updated'] > ttl:
        urls = db.execute(
            select(Urls).where(Urls.category == category)
        ).scalars().all()

        # Сохраняем только нужные данные (а не ORM-объекты)
        url_cache[category] = {
            'urls': [
                {"domain": url.domain, "url": url.url, 'network': url.network}
                for url in urls
            ],
            'last_updated': now
        }

    return url_cache[category]['urls']

async def save_visit(data: dict, request: Request, db: Session):
    ip = request.headers.get("x-real-ip", "")
    ua = request.headers.get("user-agent", "")
    language = request.headers.get("accept-language", "")
    platform = request.headers.get("sec-ch-ua-platform", "")

    visit = Visit(
        ip=ip,
        user_agent=ua,
        utm_source=data.get("utm_source", ""),
        site_id=data.get("site_id", ""),
        campaign_id=data.get("campaign_id", ""),
        teaser_id=data.get("teaser_id", ""),
        click_id=data.get("click_id", ""),
        cpc=data.get("cpc", ""),
        url=data.get("url", ""),
        content=data.get("content", ""),
        language=language,
        platform=platform,
        news_id=data.get("news_id", "")
    )

    db.add(visit)
    db.commit()
    return visit.id

@app.get("/redirect/")
async def redirect(request: Request, db: Session = Depends(get_db)):
    query = request.query_params

    urls = get_cached_urls(query.get("content", ""), db)
    if not urls:
        return {"error": f"No URLs found for category '{query.get('content')}'"}

    url_obj = random.choice(urls)
    try:
        final_url = (url_obj["domain"] + url_obj["url"]).format(
            teaser_id=query.get("teaser_id", ""),
            click_id=query.get("click_id", ""),
            campaign_id=query.get("campaign_id", ""),
            site_id=query.get("site_id", ""),
            cpc=query.get("cpc", ""),
            content=query.get("content", ""),
            utm_source=query.get("utm_source", ""),
            news_id=query.get("news_id", "")
        )
    except KeyError as e:
        return {"error": f"Missing parameter: {e}"}

    # Формируем словарь из query + url сети
    log_data = dict(query)
    log_data["url"] = url_obj.get("network", "")

    # Лог в фоне
    asyncio.create_task(save_visit(log_data, request, db))

    return RedirectResponse(final_url)



# ─────────────────────  /api/visit  ──────────────────────
@app.post("/api/visit")
async def track_visit(request: Request, db: Session = Depends(get_db)):
    try:
        data = json.loads(await request.body())
    except Exception as e:
        return {"status": "error", "detail": f"Invalid JSON: {e}"}

    visit_id = await save_visit(data, request, db)
    return {"status": "ok", "id": visit_id}

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