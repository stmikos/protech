import os, time, hashlib
from typing import Optional
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()
BITRIX = (os.getenv("BITRIX_WEBHOOK") or "").rstrip("/")
CATEGORY_ID = os.getenv("CATEGORY_ID", "0")
STAGE_ID = os.getenv("STAGE_ID", "NEW")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")
PORT = int(os.getenv("PORT", "8000"))

app = FastAPI(title="FireProtect Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if ALLOWED_ORIGINS == "*" else [o.strip() for o in ALLOWED_ORIGINS.split(",")],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

class LeadIn(BaseModel):
    name: str
    phone: str
    telegram_username: Optional[str] = None
    telegram_id: Optional[str] = None
    city: Optional[str] = None
    object_address: Optional[str] = None
    area_m2: Optional[float] = None
    height_m: Optional[float] = None
    work_type: str = Field("fire")
    complexity: str = Field("mid")
    budget_est: Optional[float] = None
    last_service_date: Optional[str] = None
    next_service_date: Optional[str] = None
    comment: Optional[str] = None
    utm_source: Optional[str] = "telegram_webapp"
    utm_campaign: Optional[str] = None

async def bx(method: str, payload: dict):
    if not BITRIX:
        raise HTTPException(500, "Bitrix webhook is not configured")
    url = f"{BITRIX}/{method}.json"
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(url, data=payload)
        data = r.json()
        if "error" in data:
            raise HTTPException(502, f"Bitrix error: {data.get('error_description') or data.get('error')}")
        return data["result"]

async def find_contact_by_phone(phone: str):
    try:
        res = await bx("crm.duplicate.findbycomm", {"entity_type":"CONTACT","type":"PHONE","values[0]":phone})
        ids = res.get("CONTACT", [])
        return int(ids[0]) if ids else None
    except HTTPException:
        return None

async def ensure_contact(p: LeadIn) -> int:
    cid = await find_contact_by_phone(p.phone)
    if cid:
        try:
            await bx("crm.contact.update", {
                "id": cid,
                "fields[UF_CRM_TELEGRAM]": p.telegram_username or "",
                "fields[PHONE][0][VALUE]": p.phone,
                "fields[PHONE][0][VALUE_TYPE]": "MOBILE",
            })
        except HTTPException: pass
        return cid
    return int(await bx("crm.contact.add", {
        "fields[NAME]": p.name or "Клиент",
        "fields[PHONE][0][VALUE]": p.phone,
        "fields[PHONE][0][VALUE_TYPE]": "MOBILE",
        "fields[UF_CRM_TELEGRAM]": p.telegram_username or "",
        "fields[SOURCE_ID]": "WEB",
        "fields[UTM_SOURCE]": p.utm_source or "",
        "fields[UTM_CAMPAIGN]": p.utm_campaign or "",
    }))

async def create_deal(contact_id: int, p: LeadIn) -> int:
    fields = {
        "TITLE": f"Огнезащита {p.object_address or p.city or ''}".strip(),
        "CONTACT_ID": contact_id, "STAGE_ID": STAGE_ID, "CATEGORY_ID": CATEGORY_ID,
        "OPPORTUNITY": p.budget_est or 0, "COMMENTS": p.comment or "",
        "UF_CRM_OBJECT_ADDRESS": p.object_address or p.city or "",
        "UF_CRM_AREA_M2": p.area_m2 or 0, "UF_CRM_HEIGHT_M": p.height_m or 0,
        "UF_CRM_WORK_TYPE": p.work_type, "UF_CRM_COMPLEXITY": p.complexity,
        "UF_CRM_LAST_SERVICE_DATE": p.last_service_date or "",
        "UF_CRM_NEXT_SERVICE_DATE": p.next_service_date or "",
        "UTM_SOURCE": p.utm_source or "", "UTM_CAMPAIGN": p.utm_campaign or "",
    }
    return int(await bx("crm.deal.add", {f"fields[{k}]": v for k, v in fields.items()}))

async def add_activity(deal_id: int, text: str, deadline_iso: Optional[str] = None):
    fields = {
        "OWNER_ID": deal_id, "OWNER_TYPE_ID": 2, "TYPE_ID": 4,
        "SUBJECT": "Follow-up по заявке из WebApp", "DESCRIPTION": text,
    }
    if deadline_iso: fields["DEADLINE"] = deadline_iso
    return await bx("crm.activity.add", {f"fields[{k}]": v for k, v in fields.items()})

@app.get('/health')\nasync def health():\n    return {'status':'ok'}\n\n@app.post('/lead')\nasync def lead(p: LeadIn):\n    key = hashlib.sha1(f\"{p.phone}|{int(time.time()/60)}\".encode()).hexdigest()\n    contact_id = await ensure_contact(p)\n    deal_id = await create_deal(contact_id, p)\n    try: await add_activity(deal_id, 'Перезвонить в течение 1 часа.')\n    except Exception: pass\n    if p.next_service_date:\n        try: await add_activity(deal_id, 'Плановый повтор огнезащиты. Связаться с клиентом.', f\"{p.next_service_date}T10:00:00+03:00\")\n        except Exception: pass\n    return {\"status\":\"ok\",\"deal_id\":deal_id,\"contact_id\":contact_id,\"key\":key}\n