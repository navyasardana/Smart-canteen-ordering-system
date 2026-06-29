# 🍽️ Smart Canteen Pre-Ordering System

A full-stack pre-ordering system for **NSUT's Nescafe canteen**. Students browse the menu, build a cart, and pick a pickup time slot — the backend assigns them to a slot using a greedy scheduling algorithm and tracks their order live from *Pending → Being Prepared → Ready for Pickup*. A separate admin dashboard lets staff manage slots, update order status, toggle menu availability, and view live analytics.

---

## 📸 Screenshots

> _Replace the placeholders below with actual screenshots._

| Screen | Preview |
|---|---|
| **Student — Menu & Cart** | `<!-- screenshot: student menu page -->` |
| **Student — Live Order Tracker** | `<!-- screenshot: order confirmation + tracker -->` |
| **Admin — Dashboard & Orders** | `<!-- screenshot: admin dashboard -->` |
| **Admin — Slot Management** | `<!-- screenshot: slot management cards -->` |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | FastAPI (Python) |
| **Database** | MongoDB Atlas |
| **Language** | Python 3.11 |
| **Server** | Uvicorn (ASGI) |
| **Scheduling** | APScheduler (daily slot reset) |
| **Frontend** | Vanilla HTML / CSS / JS |
| **Containerization** | Docker |

---

## ⚙️ How the Greedy Algorithm Works (simply)

The canteen has a handful of pickup slots, each with a limited number of spots (capacity).

When a student places an order, the system:

1. Looks at the slots **in time order — earliest first**.
2. Picks the **first slot that still has a free spot** (and isn't closed).
3. If the student requested a specific slot, that one is tried first.

That's the "greedy" part: it doesn't try every possible combination — it just grabs the earliest available option right now. It's simple, fast, and gives students the soonest possible pickup time.

```
Slots:  10:45 [FULL]   11:00 [3/5]   11:15 [0/5]   11:30 [0/5]
                          ↑
         New order → assigned to 11:00 (earliest slot with room)
```

---

## 🔒 How the Race Condition Is Handled

**The problem:** Two students could order at the *exact same time*. If the code did "read the count → check if full → then add one," both requests might read "4 booked, 1 spot left" and both get added — pushing the slot to 6 in a 5-capacity slot (overbooking).

**The fix — one atomic database operation.** Instead of reading and writing separately, we use MongoDB's `findOneAndUpdate` with a condition baked into the query:

```python
slots_col.find_one_and_update(
    {"slot_id": slot_id, "booked": {"$lt": capacity}},  # only if a spot is free
    {"$inc": {"booked": 1}},                            # claim it
    return_document=True,
)
```

MongoDB guarantees this find-and-increment happens as a **single, indivisible step**. If two orders race for the last spot, only one succeeds — the other gets `None` back and automatically moves on to the next available slot. No overbooking, no locks needed.

The same atomic `booked` value is also used as the student's **queue position**, so positions can never collide either.

---

## 🚀 Run Locally

**Prerequisites:** Python 3.11+, a MongoDB Atlas connection string.

```bash
# 1. Clone and enter the project
git clone <your-repo-url>
cd smart-canteen-ordering-system

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your MongoDB connection string to a .env file
echo "MONGO_URL=your_mongodb_atlas_connection_string" > .env

# 5. Start the server
uvicorn main:app --reload
```

Then open:

- **Student app:** http://127.0.0.1:8000
- **Admin dashboard:** http://127.0.0.1:8000/admin
- **API docs (Swagger):** http://127.0.0.1:8000/docs

---

## 🐳 Run with Docker

**Prerequisites:** Docker installed, and a `.env` file containing your `MONGO_URL`.

```bash
# Build the image
docker build -t smart-canteen .

# Run the container (passes your .env into the container)
docker run -p 8000:8000 --env-file .env smart-canteen
```

The app will be available at **http://127.0.0.1:8000**.

> The `.env` file is intentionally excluded from the image via `.dockerignore`, so your database credentials are never baked into the build — they're injected at runtime with `--env-file`.

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/order` | Place an order; returns assigned slot + queue position |
| `GET` | `/orders` | All orders |
| `GET` | `/orders/{slot_id}` | Orders for a specific slot |
| `PATCH` | `/order/{order_id}/status` | Update order status |
| `GET` | `/queue/{slot_id}` | Queue for a slot |
| `GET` | `/slots` | Current slot availability |
| `GET` | `/slots/waittime` | Estimated wait time per slot |
| `PATCH` | `/slot/{slot_id}` | Set slot wait time / open-close a slot |
| `GET` | `/menu` | Full menu with availability |
| `PATCH` | `/menu/{item_id}` | Toggle item availability |
| `GET` | `/student/{student_id}/history` | A student's last 3 orders |
| `GET` | `/admin/overview` | Dashboard analytics |

---

## 🗂️ Project Structure

```
smart-canteen-ordering-system/
├── main.py            # FastAPI app + all endpoints
├── database.py        # MongoDB connection, slot/menu setup, daily reset
├── models.py          # Pydantic request models + validation
├── scheduler.py       # APScheduler midnight reset job
├── static/
│   ├── index.html     # Student ordering app
│   ├── admin.html     # Admin dashboard
│   └── style.css      # Shared styles
├── Dockerfile
├── requirements.txt
├── .dockerignore
├── .gitignore
├── .env               # MONGO_URL (not committed)
└── README.md
```
