slots = [
    {"slot_id": 1, "time": "10:45", "capacity": 5, "booked": 0},
    {"slot_id": 2, "time": "11:00", "capacity": 5, "booked": 0},
    {"slot_id": 3, "time": "11:15", "capacity": 5, "booked": 0},
    {"slot_id": 4, "time": "11:30", "capacity": 5, "booked": 0},
]

def assign_slot(student_id, items):
    for slot in slots:
        if slot["booked"] < slot["capacity"]:
            slot["booked"] += 1
            return {
                "student_id": student_id,
                "items": items,
                "assigned_slot": slot["time"],
                "slot_id": slot["slot_id"]
            }
    return {"error": "No slots available"}

# Test it
print(assign_slot("student_1", ["sandwich", "juice"]))
print(assign_slot("student_2", ["pizza"]))