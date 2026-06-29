from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from bson import ObjectId
from datetime import datetime

from database import orders_col, slots_col, menu_col, init_slots, init_menu
from models import OrderRequest, StatusUpdate, SlotUpdate
from scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_slots()
    init_menu()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="NSUT Nescafe Smart Canteen", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Pages ──────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def student_page():
    return FileResponse("static/index.html")

@app.get("/admin", include_in_schema=False)
def admin_page():
    return FileResponse("static/admin.html")


# ── Greedy slot assignment ─────────────────────────────────────────────────────

def assign_slot_atomic(preferred_slot_id: int | None = None) -> dict | None:
    """
    Greedy interval scheduling with atomic MongoDB operation.
    If student prefers a specific slot, try that first; else use earliest available.
    Uses findOneAndUpdate so the find+increment is a single atomic op — race-condition safe.
    """
    slots = list(slots_col.find({"closed": False}, {"_id": 0}).sort("slot_id", 1))

    # Put preferred slot first if specified
    if preferred_slot_id:
        slots.sort(key=lambda s: (0 if s["slot_id"] == preferred_slot_id else 1, s["slot_id"]))

    for slot in slots:
        updated = slots_col.find_one_and_update(
            {"slot_id": slot["slot_id"], "booked": {"$lt": slot["capacity"]}, "closed": False},
            {"$inc": {"booked": 1}},
            return_document=True,
        )
        if updated:
            return updated

    return None


# ── Orders ─────────────────────────────────────────────────────────────────────

@app.post("/order")
def place_order(order: OrderRequest):
    slot = assign_slot_atomic(order.slot_id)
    if not slot:
        raise HTTPException(status_code=409, detail="No slots available right now. Please try later.")

    # The atomic $inc in assign_slot_atomic already returned the post-increment
    # booked count — that IS this order's collision-free position in the slot.
    queue_position = slot["booked"]
    # Estimated ready time: wait_time minutes per order ahead in queue
    estimated_mins = slot.get("wait_time", 5) * queue_position

    doc = {
        "student_name": order.student_name,
        "student_id": order.student_id,
        "items": order.items,
        "quantity": order.quantity,
        "assigned_slot": slot["time"],
        "slot_id": slot["slot_id"],
        "status": "Pending",
        "queue_position": queue_position,
        "estimated_mins": estimated_mins,
        "created_at": datetime.utcnow().isoformat(),
    }
    result = orders_col.insert_one(doc)
    order_id = str(result.inserted_id)
    orders_col.update_one({"_id": result.inserted_id}, {"$set": {"order_id": order_id}})

    return {
        "order_id": order_id,
        "student_name": order.student_name,
        "student_id": order.student_id,
        "items": order.items,
        "quantity": order.quantity,
        "assigned_slot": slot["time"],
        "slot_id": slot["slot_id"],
        "queue_position": queue_position,
        "estimated_mins": estimated_mins,
        "status": "Pending",
    }


@app.get("/orders")
def get_all_orders():
    orders = list(orders_col.find({}, {"_id": 0}))
    # Backfill missing fields for old orders
    for o in orders:
        o.setdefault("order_id", "")
        o.setdefault("status", "Pending")
        o.setdefault("queue_position", 0)
        o.setdefault("estimated_mins", 0)
    return {"orders": orders}


@app.get("/orders/{slot_id}")
def get_orders_by_slot(slot_id: int):
    orders = list(orders_col.find({"slot_id": slot_id}, {"_id": 0}))
    for o in orders:
        o.setdefault("status", "Pending")
        o.setdefault("queue_position", 0)
    return {"slot_id": slot_id, "orders": orders}


@app.patch("/order/{order_id}/status")
def update_order_status(order_id: str, update: StatusUpdate):
    try:
        oid = ObjectId(order_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid order_id")

    result = orders_col.find_one_and_update(
        {"_id": oid},
        {"$set": {"status": update.status}},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Order not found")

    return {
        "order_id": order_id,
        "status": result["status"],
        "student_name": result["student_name"],
        "assigned_slot": result["assigned_slot"],
    }


# ── Queue & slots ──────────────────────────────────────────────────────────────

@app.get("/queue/{slot_id}")
def get_queue(slot_id: int):
    orders = list(orders_col.find({"slot_id": slot_id}, {"_id": 0}).sort("queue_position", 1))
    return {"slot_id": slot_id, "queue_length": len(orders), "queue": orders}


@app.get("/slots")
def get_slots():
    slots = list(slots_col.find({}, {"_id": 0}).sort("slot_id", 1))
    return {"slots": slots}


@app.get("/slots/waittime")
def get_wait_times():
    """Return estimated wait time per slot based on pending order count."""
    slots = list(slots_col.find({}, {"_id": 0}).sort("slot_id", 1))
    result = []
    for slot in slots:
        pending = orders_col.count_documents({
            "slot_id": slot["slot_id"],
            "status": {"$in": ["Pending", "Being Prepared"]}
        })
        wait = slot.get("wait_time", 5) * max(pending, 1)
        result.append({
            "slot_id": slot["slot_id"],
            "time": slot["time"],
            "booked": slot["booked"],
            "capacity": slot["capacity"],
            "closed": slot.get("closed", False),
            "estimated_wait_mins": wait,
            "available": not slot.get("closed", False) and slot["booked"] < slot["capacity"],
        })
    return {"slots": result}


@app.patch("/slot/{slot_id}")
def update_slot(slot_id: int, update: SlotUpdate):
    """Admin: set wait_time or close/open a slot."""
    fields = {}
    if update.wait_time is not None:
        fields["wait_time"] = update.wait_time
    if update.closed is not None:
        fields["closed"] = update.closed

    if not fields:
        raise HTTPException(status_code=400, detail="Nothing to update")

    result = slots_col.find_one_and_update(
        {"slot_id": slot_id},
        {"$set": fields},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Slot not found")

    result.pop("_id", None)
    return result


# ── Menu ───────────────────────────────────────────────────────────────────────

@app.get("/menu")
def get_menu():
    items = list(menu_col.find({}, {"_id": 0}))
    return {"menu": items}


@app.patch("/menu/{item_id}")
def toggle_menu_item(item_id: str):
    """Admin: flip available flag for a menu item."""
    item = menu_col.find_one({"item_id": item_id})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    new_val = not item["available"]
    menu_col.update_one({"item_id": item_id}, {"$set": {"available": new_val}})
    return {"item_id": item_id, "available": new_val}


# ── Student history ────────────────────────────────────────────────────────────

@app.get("/student/{student_id}/history")
def get_student_history(student_id: str):
    """Return last 3 orders for a student (for Order Again feature)."""
    orders = list(
        orders_col.find({"student_id": student_id}, {"_id": 0})
        .sort("created_at", -1)
        .limit(3)
    )
    return {"student_id": student_id, "history": orders}


# ── Admin analytics ────────────────────────────────────────────────────────────

@app.get("/admin/overview")
def admin_overview():
    """Today's summary cards for the admin dashboard."""
    total_orders = orders_col.count_documents({})

    # Most ordered item
    pipeline = [
        {"$unwind": "$items"},
        {"$group": {"_id": "$items", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 1},
    ]
    top = list(orders_col.aggregate(pipeline))
    top_item = top[0]["_id"] if top else "—"

    # Busiest slot
    slot_pipeline = [
        {"$group": {"_id": "$slot_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 1},
    ]
    top_slot = list(orders_col.aggregate(slot_pipeline))
    busiest_slot_id = top_slot[0]["_id"] if top_slot else None
    busiest_slot = None
    if busiest_slot_id:
        s = slots_col.find_one({"slot_id": busiest_slot_id}, {"_id": 0})
        busiest_slot = s["time"] if s else str(busiest_slot_id)

    # Revenue estimate (sum of all order quantities × avg price ₹45)
    revenue_pipeline = [{"$group": {"_id": None, "total": {"$sum": "$quantity"}}}]
    rev = list(orders_col.aggregate(revenue_pipeline))
    estimated_revenue = (rev[0]["total"] if rev else 0) * 45

    # Orders per slot for bar chart
    per_slot = list(orders_col.aggregate([
        {"$group": {"_id": "$assigned_slot", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]))

    return {
        "total_orders": total_orders,
        "estimated_revenue": estimated_revenue,
        "busiest_slot": busiest_slot or "—",
        "top_item": top_item,
        "orders_per_slot": [{"slot": x["_id"], "count": x["count"]} for x in per_slot],
    }
