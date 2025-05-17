import uvicorn
from fastapi import FastAPI, Query, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import os
import uuid
import shutil
import threading
import time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

download_status = {}
download_files = {}

def download_video_task(url: str, quality: str, download_id: str, cookie_path: str = None):
    filename = f"/tmp/{download_id}.mp4"

    format_map = {
        "audio": "bestaudio",
        "video": "bestvideo",
        "audio+video": "bestvideo+bestaudio/best",
        "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
        "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
        "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "1440p": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
        "2160p": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
    }
    selected_format = format_map.get(quality.lower(), "best")

    def progress_hook(d):
        if d["status"] == "downloading":
            percent = d.get("_percent_str", "0%").replace("%", "").strip()
            try:
                download_status[download_id] = {
                    "progress": float(percent),
                    "status": "Downloading...",
                }
            except ValueError:
                pass
        elif d["status"] == "finished":
            download_status[download_id] = {"progress": 100.0, "status": "Processing..."}

    ydl_opts = {
        "format": selected_format,
        "merge_output_format": "mp4",
        "outtmpl": filename,
        "progress_hooks": [progress_hook],
        "quiet": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        }
    }

    if cookie_path:
        ydl_opts["cookiefile"] = cookie_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        download_status[download_id] = {"progress": 100.0, "status": "Finished"}
        download_files[download_id] = filename
    except Exception as e:
        download_status[download_id] = {"progress": 0.0, "status": f"Error: {str(e)}"}

@app.post("/download")
async def download(
    url: str = Query(...),
    quality: str = Query("best"),
    id: str = Query(None),
    cookiefile: UploadFile = File(None),
):
    download_id = id or str(uuid.uuid4())
    cookie_path = None
    if cookiefile is not None:
        cookie_path = f"/tmp/{download_id}_cookies.txt"
        with open(cookie_path, "wb") as f:
            shutil.copyfileobj(cookiefile.file, f)

    download_status[download_id] = {"progress": 0.0, "status": "Starting"}

    thread = threading.Thread(target=download_video_task, args=(url, quality, download_id, cookie_path))
    thread.start()

    return {"download_id": download_id, "status": "Download started"}

@app.get("/status")
async def status(id: str = Query(...)):
    if id not in download_status:
        raise HTTPException(status_code=404, detail="Download ID not found")
    return download_status[id]

@app.get("/file")
async def get_file(id: str = Query(...), background_tasks: BackgroundTasks = None):
    if id not in download_files:
        raise HTTPException(status_code=404, detail="File not ready or download ID not found")

    filepath = download_files[id]
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    def cleanup():
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
            download_files.pop(id, None)
            download_status.pop(id, None)
        except Exception:
            pass

    if background_tasks:
        background_tasks.add_task(cleanup)

    return FileResponse(filepath, filename="video.mp4", media_type="video/mp4")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=5000)

