from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime, timedelta
import os
import certifi

load_dotenv()

client = MongoClient(os.getenv("MONGO_URL"), tlsCAFile=certifi.where())

db = client["canteen"]
orders_col = db["orders"]
slots_col = db["slots"]
menu_col = db["menu"]

SLOT_GAP_MINUTES = 15  # minutes between pickup slots
NUM_SLOTS = 4


def generate_slot_times():
    """
    Build 4 rolling pickup slots starting from the next 15-minute boundary
    after the current local time. e.g. at 7:02 → 7:15, 7:30, 7:45, 8:00.
    """
    now = datetime.now()
    # Round up to the next SLOT_GAP_MINUTES boundary
    minutes_to_add = SLOT_GAP_MINUTES - (now.minute % SLOT_GAP_MINUTES)
    start = (now + timedelta(minutes=minutes_to_add)).replace(second=0, microsecond=0)
    return [(start + timedelta(minutes=SLOT_GAP_MINUTES * i)).strftime("%H:%M")
            for i in range(NUM_SLOTS)]

MENU_ITEMS = [
    # Maggi
    {"item_id": "m1", "name": "Maggi Classic",       "category": "Maggi",      "price": 40,  "available": True},
    {"item_id": "m2", "name": "Cheese Maggi",         "category": "Maggi",      "price": 55,  "available": True},
    {"item_id": "m3", "name": "Oregano Maggi",        "category": "Maggi",      "price": 50,  "available": True},
    {"item_id": "m4", "name": "Masala Maggi",         "category": "Maggi",      "price": 45,  "available": True},
    {"item_id": "m5", "name": "Double Masala Maggi",  "category": "Maggi",      "price": 60,  "available": True},
    # Pasta
    {"item_id": "p1", "name": "Arrabiata Pasta",      "category": "Pasta",      "price": 70,  "available": True},
    {"item_id": "p2", "name": "White Sauce Pasta",    "category": "Pasta",      "price": 75,  "available": True},
    {"item_id": "p3", "name": "Pesto Pasta",          "category": "Pasta",      "price": 80,  "available": True},
    {"item_id": "p4", "name": "Mac and Cheese",       "category": "Pasta",      "price": 85,  "available": True},
    # Sandwiches
    {"item_id": "s1", "name": "Veg Grilled Sandwich", "category": "Sandwiches", "price": 60,  "available": True},
    {"item_id": "s2", "name": "Cheese Sandwich",      "category": "Sandwiches", "price": 65,  "available": True},
    {"item_id": "s3", "name": "Paneer Sandwich",      "category": "Sandwiches", "price": 75,  "available": True},
    {"item_id": "s4", "name": "Club Sandwich",        "category": "Sandwiches", "price": 80,  "available": True},
    # Hot Drinks
    {"item_id": "h1", "name": "Nescafe Classic",      "category": "Hot Drinks", "price": 20,  "available": True},
    {"item_id": "h2", "name": "Cappuccino",           "category": "Hot Drinks", "price": 35,  "available": True},
    {"item_id": "h3", "name": "Latte",                "category": "Hot Drinks", "price": 40,  "available": True},
    {"item_id": "h4", "name": "Cold Coffee",          "category": "Hot Drinks", "price": 45,  "available": True},
    {"item_id": "h5", "name": "Masala Chai",          "category": "Hot Drinks", "price": 15,  "available": True},
    {"item_id": "h6", "name": "Ginger Chai",          "category": "Hot Drinks", "price": 15,  "available": True},
    {"item_id": "h7", "name": "Green Tea",            "category": "Hot Drinks", "price": 20,  "available": True},
    # Ice Teas
    {"item_id": "i1", "name": "Lemon Ice Tea",        "category": "Ice Teas",   "price": 50,  "available": True},
    {"item_id": "i2", "name": "Peach Ice Tea",        "category": "Ice Teas",   "price": 55,  "available": True},
    {"item_id": "i3", "name": "Mango Ice Tea",        "category": "Ice Teas",   "price": 55,  "available": True},
    {"item_id": "i4", "name": "Passion Fruit Ice Tea","category": "Ice Teas",   "price": 60,  "available": True},
    # Bakery
    {"item_id": "b1", "name": "Chocolate Brownie",   "category": "Bakery",     "price": 40,  "available": True},
    {"item_id": "b2", "name": "Cookies",              "category": "Bakery",     "price": 25,  "available": True},
    {"item_id": "b3", "name": "Croissant",            "category": "Bakery",     "price": 45,  "available": True},
    {"item_id": "b4", "name": "Vada Pav",             "category": "Bakery",     "price": 20,  "available": True},
    {"item_id": "b5", "name": "Samosa",               "category": "Bakery",     "price": 15,  "available": True},
    {"item_id": "b6", "name": "Pastry",               "category": "Bakery",     "price": 35,  "available": True},
    {"item_id": "b7", "name": "Muffin",               "category": "Bakery",     "price": 40,  "available": True},
    {"item_id": "b8", "name": "Cake Slice",           "category": "Bakery",     "price": 50,  "available": True},
]


def init_slots():
    """
    Create or refresh the 4 rolling slots. Slot times are always regenerated
    relative to the current time so they stay in sync with the real clock.
    Booked counts are reset since the time windows have moved.
    """
    times = generate_slot_times()
    slots_col.delete_many({})
    slots_col.insert_many([
        {"slot_id": i + 1, "time": times[i], "capacity": 5,
         "booked": 0, "closed": False, "wait_time": 5}
        for i in range(NUM_SLOTS)
    ])


def init_menu():
    if menu_col.count_documents({}) == 0:
        menu_col.insert_many(MENU_ITEMS)


def reset_slots():
    """Roll slot times forward and reset booked counts. Called at midnight."""
    init_slots()
