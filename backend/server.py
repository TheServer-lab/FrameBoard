import os, json, time
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from pymongo import MongoClient
import gridfs
from bson import ObjectId
from utils.thumbnails import create_thumbnail

# -------------------------------------------------------------------
# Load config
# -------------------------------------------------------------------
if not os.path.exists("config.json"):
    raise RuntimeError("Missing config.json! Copy config.example.json")

with open("config.json") as f:
    config = json.load(f)

MONGO = config["mongo_url"]
ADMIN_KEY = config["admin_key"]

client = MongoClient(MONGO)
db = client["frameboard"]
fs = gridfs.GridFS(db)

app = FastAPI()

# -------------------------------------------------------------------
# Create thread (OP)
# -------------------------------------------------------------------
@app.post("/api/thread")
async def create_thread(
    room: str = Form(...),
    text: str = Form(""),
    file: UploadFile = File(None)
):
    if room not in get_rooms_list():
        create_room(room)

    image_id = None
    thumb_id = None

    if file:
        data = await file.read()

        # store full image
        image_id = fs.put(data, filename=file.filename)

        # store thumbnail
        thumb_data = create_thumbnail(data)
        thumb_id = fs.put(thumb_data, filename="thumb_" + file.filename)

    thread = {
        "op": True,
        "room": room,
        "text": text,
        "image_id": str(image_id) if image_id else None,
        "thumbnail_id": str(thumb_id) if thumb_id else None,
        "created": int(time.time())
    }

    result = db[f"threads_{room}"].insert_one(thread)
    thread["_id"] = str(result.inserted_id)

    return {"status": "ok", "thread": thread}

# -------------------------------------------------------------------
# Reply to thread
# -------------------------------------------------------------------
@app.post("/api/reply")
async def reply(
    room: str = Form(...),
    thread_id: str = Form(...),
    text: str = Form(""),
    file: UploadFile = File(None)
):
    image_id = None
    thumb_id = None

    if file:
        data = await file.read()
        image_id = fs.put(data)
        thumb_data = create_thumbnail(data)
        thumb_id = fs.put(thumb_data)

    reply = {
        "op": False,
        "room": room,
        "thread_id": thread_id,
        "text": text,
        "image_id": str(image_id) if image_id else None,
        "thumbnail_id": str(thumb_id) if thumb_id else None,
        "created": int(time.time())
    }

    db[f"threads_{room}"].update_one(
        {"_id": ObjectId(thread_id)},
        {"$push": {"replies": reply}}
    )

    return {"status": "ok", "reply": reply}

# -------------------------------------------------------------------
# Get all threads in room
# -------------------------------------------------------------------
@app.get("/api/threads/{room}")
def get_threads(room: str):
    docs = list(db[f"threads_{room}"].find())
    for d in docs:
        d["_id"] = str(d["_id"])
    return {"threads": docs}

# -------------------------------------------------------------------
# Get single thread
# -------------------------------------------------------------------
@app.get("/api/thread/{room}/{thread_id}")
def get_thread(room: str, thread_id: str):
    doc = db[f"threads_{room}"].find_one({"_id": ObjectId(thread_id)})
    if not doc:
        raise HTTPException(404, "Thread Not Found")
    doc["_id"] = str(doc["_id"])
    return doc

# -------------------------------------------------------------------
# Serve image
# -------------------------------------------------------------------
@app.get("/api/image/{image_id}")
def get_image(image_id: str):
    try:
        file = fs.get(ObjectId(image_id))
    except:
        raise HTTPException(404)
    return Response(file.read(), media_type="image/jpeg")

# -------------------------------------------------------------------
# Serve thumbnail
# -------------------------------------------------------------------
@app.get("/api/thumb/{thumb_id}")
def get_thumb(thumb_id: str):
    try:
        file = fs.get(ObjectId(thumb_id))
    except:
        raise HTTPException(404)
    return Response(file.read(), media_type="image/jpeg")

# -------------------------------------------------------------------
# Rooms
# -------------------------------------------------------------------
def get_rooms_list():
    return [r["name"] for r in db.rooms.find()]

def create_room(name):
    db.rooms.insert_one({"name": name})

@app.get("/api/rooms")
def get_rooms():
    rooms = list(db.rooms.find({}, {"_id": 0}))
    return {"rooms": rooms}

# -------------------------------------------------------------------
# Admin API
# -------------------------------------------------------------------
@app.delete("/api/admin/thread")
def admin_delete_thread(room: str, thread_id: str, key: str):
    if key != ADMIN_KEY:
        raise HTTPException(403)

    db[f"threads_{room}"].delete_one({"_id": ObjectId(thread_id)})
    return {"status": "deleted"}
