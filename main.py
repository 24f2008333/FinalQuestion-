from fastapi import FastAPI, Header, Response, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uuid
import time
import base64

app = FastAPI()

TOTAL_ORDERS = 50
RATE_LIMIT = 20
WINDOW = 10

@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.method == "GET" and request.url.path == "/orders":
        return await call_next(request)

    client = request.headers.get("X-Client-Id", "anonymous")
    now = time.time()

    bucket = client_requests.setdefault(client, [])
    bucket[:] = [t for t in bucket if now - t < WINDOW]

    if len(bucket) >= RATE_LIMIT:
        retry = max(1, int(WINDOW - (now - bucket[0])))
        return Response(
            status_code=429,
            headers={"Retry-After": str(retry)}
        )

    bucket.append(now)
    return await call_next(request) 

@app.post("/orders", status_code=201)
def create_order(order: OrderCreate,
                 idempotency_key: str = Header(..., alias="Idempotency-Key")):

    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    new_order = {
        "id": str(uuid.uuid4()),
        "item": order.item,
        "quantity": order.quantity
    }

    idempotency_store[idempotency_key] = new_order
    return new_order

@app.get("/orders")
def list_orders(limit: int = 10, cursor: Optional[str] = None):
    start = decode_cursor(cursor)
    end = min(start + limit, TOTAL_ORDERS)

    items = [{"id": i} for i in range(start + 1, end + 1)]

    next_cursor = encode_cursor(end) if end < TOTAL_ORDERS else None

    return {
        "items": items,
        "next_cursor": next_cursor
    }