# Smart Canteen Pre-Ordering System

A backend API that lets students pre-order canteen food and get assigned to a pickup time slot automatically using a greedy interval scheduling algorithm.

## Tech Stack

| Layer | Tool |
|---|---|
| Framework | FastAPI |
| Server | Uvicorn |
| Database | MongoDB Atlas (via PyMongo) |
| Config | python-dotenv |
| Language | Python 3.10+ |

## How the Greedy Algorithm Works

The system has 4 pickup slots (10:45, 11:00, 11:15, 11:30), each with a capacity of 5 orders.

When a student places an order, the algorithm:
1. Fetches all slots sorted by `slot_id` (earliest first).
2. Iterates through them in order.
3. Assigns the **first slot** where `booked < capacity`.
4. Increments that slot's `booked` count atomically in MongoDB.

This is a greedy approach — it makes the locally optimal choice (earliest available slot) at each step without backtracking. Because slots are ordered chronologically and capacity is enforced in the database, the algorithm is both simple and collision-safe.

If all slots are full, the API returns a `409 Conflict` error.

## Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/order` | Place an order; returns the assigned slot |
| `GET` | `/orders` | List all orders |
| `GET` | `/slots` | Current state of all slots |

### POST /order — request body

```json
{
  "student_name": "Navya",
  "student_id": "S001",
  "items": ["sandwich", "juice"],
  "quantity": 2
}
```

## Setup

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd smart-canteen-ordering-system

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install fastapi uvicorn pymongo python-dotenv

# 4. Add your MongoDB connection string
echo "MONGO_URL=your_connection_string_here" > .env

# 5. Run the server
uvicorn main:app --reload
```

The API will be live at `http://127.0.0.1:8000`.  
Interactive docs: `http://127.0.0.1:8000/docs`

## Slot Persistence

Slots are stored in MongoDB (`canteen.slots` collection). On first startup, the four default slots are inserted automatically. Subsequent restarts preserve the current `booked` counts, so slot state survives server restarts.
