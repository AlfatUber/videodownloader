from fastapi import FastAPI, Query, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import os
import uuid

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

download_status = {}

def download_video(url: str, format_str: str, download_id: str):
    filename = f"/tmp/{download_id}.mp4"

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
            download_status[download_id] = {"progress": 100.0, "status": "Finished"}

    ydl_opts = {
        "format": format_str,
        "merge_output_format": "mp4",
        "outtmpl": filename,
        "progress_hooks": [progress_hook],
        "quiet": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        download_status[download_id] = {"progress": 0, "status": f"Error: {str(e)}"}

@app.get("/download")
def start_download(url: str = Query(...), quality: str = Query("best"), background_tasks: BackgroundTasks = None):
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
    download_id = str(uuid.uuid4())
    download_status[download_id] = {"progress": 0, "status": "Starting"}

    background_tasks.add_task(download_video, url, selected_format, download_id)
    return {"download_id": download_id, "message": "Download started"}

@app.get("/progress")
def get_progress(id: str = Query(...)):
    return download_status.get(id, {"progress": 0, "status": "Not found"})

@app.get("/file")
def get_file(id: str = Query(...)):
    filename = f"/tmp/{id}.mp4"
    if os.path.exists(filename):
        return FileResponse(filename, filename="video.mp4", media_type="video/mp4")
    else:
        raise HTTPException(status_code=404, detail="File not found")

@app.delete("/file")
def delete_file(id: str = Query(...)):
    filename = f"/tmp/{id}.mp4"
    if os.path.exists(filename):
        os.remove(filename)
        download_status.pop(id, None)
        return {"message": "File deleted"}
    else:
        raise HTTPException(status_code=404, detail="File not found")
