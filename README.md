# Smart Canteen Pre-Ordering System

A production-ready backend + frontend for a college canteen pre-ordering system. Students pick up food at an assigned time slot. The system uses a greedy scheduling algorithm and atomic MongoDB operations to fairly assign slots without race conditions.

---

## System Architecture

```
Browser (HTML/CSS/JS)
        │
        ▼
FastAPI (main.py)           ← REST API + static file serving
    ├── models.py            ← Pydantic request validation
    ├── database.py          ← MongoDB connection + slot helpers
    └── scheduler.py         ← APScheduler midnight reset job
        │
        ▼
MongoDB Atlas
    ├── canteen.slots        ← 4 slots, capacity + booked count
    └── canteen.orders       ← all student orders
```

**Request flow for POST /order:**
1. Pydantic validates the request body (student ID alphanumeric, quantity ≤ 10, items not empty)
2. `assign_slot_atomic()` runs the greedy algorithm with an atomic MongoDB operation
3. Order is saved to MongoDB with status `Pending` and a queue position
4. Response returns the assigned slot and queue position

---

## Greedy Interval Scheduling Algorithm

The system has 4 pickup slots (10:45, 11:00, 11:15, 11:30), each with a capacity of 5 orders.

**The algorithm:**
1. Fetch all slots sorted by `slot_id` (chronological order — earliest first)
2. Iterate through each slot
3. Assign the **first slot** where `booked < capacity`
4. Increment that slot's `booked` count

This is greedy because it always takes the locally optimal choice (earliest available slot) without looking ahead. It's O(n) on the number of slots — fine for a small fixed set.

---

## The Race Condition & How It's Fixed

**The problem:** Without atomic operations, two simultaneous requests could both read a slot as `booked: 4` (one below capacity), both decide it's available, and both increment — resulting in `booked: 6` on a capacity-5 slot.

**The fix — `findOneAndUpdate` with a conditional filter:**

```python
slots_col.find_one_and_update(
    {"slot_id": slot["slot_id"], "booked": {"$lt": slot["capacity"]}},
    {"$inc": {"booked": 1}},
    return_document=True,
)
```

MongoDB executes the **find + update as a single atomic operation** at the database level. The filter `"booked": {"$lt": capacity}` means the update only succeeds if the slot still has room *at the exact moment of the write*. If two requests race, only one wins — the other gets `None` back and tries the next slot.

No locks, no transactions needed. This is the correct way to handle this in MongoDB.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Framework | FastAPI |
| Server | Uvicorn |
| Database | MongoDB Atlas (PyMongo) |
| Scheduling | APScheduler |
| Validation | Pydantic v2 |
| Frontend | Vanilla HTML / CSS / JS |
| Config | python-dotenv |

---

## Project Structure

```
smart-canteen-ordering-system/
├── main.py          # FastAPI app, all endpoints
├── database.py      # MongoDB connection, slot init + reset
├── models.py        # Pydantic request/response models
├── scheduler.py     # APScheduler daily midnight reset
├── static/
│   ├── index.html   # Student order page
│   ├── admin.html   # Admin dashboard
│   └── style.css    # Shared styles
├── .env             # MONGO_URL (not committed)
├── .gitignore
└── README.md
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/order` | Place an order; returns slot + queue position |
| `GET` | `/orders` | All orders |
| `GET` | `/orders/{slot_id}` | Orders for a specific slot |
| `PATCH` | `/order/{order_id}/status` | Update status: Pending → Ready → Collected |
| `GET` | `/queue/{slot_id}` | Ordered queue for a slot |
| `GET` | `/slots` | Current slot availability |

### POST /order — request body
```json
{
  "student_name": "Navya",
  "student_id": "S001",
  "items": ["sandwich", "juice"],
  "quantity": 2
}
```

**Validation rules:**
- `student_id` — alphanumeric only
- `quantity` — between 1 and 10
- `items` — cannot be empty

---

## Local Setup

```bash
# 1. Clone the repo
git clone <repo-url>
cd smart-canteen-ordering-system

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install fastapi uvicorn pymongo python-dotenv apscheduler certifi

# 4. Set your MongoDB connection string
echo "MONGO_URL=mongodb+srv://<user>:<pass>@cluster0.xxxxx.mongodb.net/?appName=Cluster0" > .env

# 5. Start the server
uvicorn main:app --reload
```

- Student page: `http://127.0.0.1:8000`
- Admin page:   `http://127.0.0.1:8000/admin`
- API docs:     `http://127.0.0.1:8000/docs`

---

## Daily Reset

APScheduler runs a background job every day at midnight that resets all `booked` counts to 0. This means slots automatically clear for the next day without any manual intervention or server restart.
