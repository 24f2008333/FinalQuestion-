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

# Storage
idempotency_store = {}
client_requests = {}

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class OrderCreate(BaseModel):
    item: Optional[str] = None
    quantity: Optional[int] = 1


def encode_cursor(i):
    return base64.urlsafe_b64encode(str(i).encode()).decode()


def decode_cursor(c):
    if not c:
        return 0

    try:
        return int(base64.urlsafe_b64decode(c.encode()).decode())
    except:
        raise HTTPException(status_code=400, detail="Invalid cursor")


@app.middleware("http")
async def rate_limit(request: Request, call_next):

    # Only rate limit when X-Client-Id is provided
    client = request.headers.get("X-Client-Id")

    if client is None:
        return await call_next(request)

    now = time.time()

    bucket = client_requests.setdefault(client, [])

    bucket[:] = [
        t for t in bucket
        if now - t < WINDOW
    ]

    if len(bucket) >= RATE_LIMIT:
        retry = max(1, int(WINDOW - (now - bucket[0])))

        return Response(
            status_code=429,
            headers={
                "Retry-After": str(retry)
            }
        )

    bucket.append(now)

    return await call_next(request)

@app.post("/orders", status_code=201)
def create_order(
    order: OrderCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key")
):

    # Return same order for same key
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

    items = [
        {
            "id": i,
            "item": f"Order {i}"
        }
        for i in range(start + 1, end + 1)
    ]

    next_cursor = encode_cursor(end) if end < TOTAL_ORDERS else None

    return {
        "items": items,
        "next_cursor": next_cursor
    }