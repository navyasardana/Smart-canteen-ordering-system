from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import certifi

load_dotenv()

app = FastAPI(title="Smart Canteen Ordering System")

client = MongoClient(os.getenv("MONGO_URL"), tlsCAFile=certifi.where())
db = client["canteen"]
orders_col = db["orders"]
slots_col = db["slots"]

INITIAL_SLOTS = [
    {"slot_id": 1, "time": "10:45", "capacity": 5, "booked": 0},
    {"slot_id": 2, "time": "11:00", "capacity": 5, "booked": 0},
    {"slot_id": 3, "time": "11:15", "capacity": 5, "booked": 0},
    {"slot_id": 4, "time": "11:30", "capacity": 5, "booked": 0},
]


def init_slots():
    if slots_col.count_documents({}) == 0:
        slots_col.insert_many(INITIAL_SLOTS)


init_slots()


class Order(BaseModel):
    student_name: str
    student_id: str
    items: List[str]
    quantity: int


def assign_slot() -> dict | None:
    """Greedy interval scheduling: pick the earliest slot that still has capacity."""
    slots = list(slots_col.find({}, {"_id": 0}).sort("slot_id", 1))
    for slot in slots:
        if slot["booked"] < slot["capacity"]:
            slots_col.update_one(
                {"slot_id": slot["slot_id"]},
                {"$inc": {"booked": 1}}
            )
            return slot
    return None


@app.get("/")
def root():
    return {"message": "Smart Canteen API is running"}


@app.post("/order")
def place_order(order: Order):
    slot = assign_slot()
    if not slot:
        raise HTTPException(status_code=409, detail="No slots available, please try later")

    doc = {
        "student_name": order.student_name,
        "student_id": order.student_id,
        "items": order.items,
        "quantity": order.quantity,
        "assigned_slot": slot["time"],
        "slot_id": slot["slot_id"],
    }
    orders_col.insert_one(doc)

    return {
        "student_name": order.student_name,
        "student_id": order.student_id,
        "items": order.items,
        "quantity": order.quantity,
        "assigned_slot": slot["time"],
        "slot_id": slot["slot_id"],
    }


@app.get("/orders")
def get_orders():
    orders = list(orders_col.find({}, {"_id": 0}))
    return {"orders": orders}


@app.get("/slots")
def get_slots():
    slots = list(slots_col.find({}, {"_id": 0}).sort("slot_id", 1))
    return {"slots": slots}
