import uvicorn
from fastapi import FastAPI, Query, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import os
import uuid
import shutil

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

def download_video_task(url, quality, download_id, cookie_path=None):
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
            percent_str = d.get("_percent_str", "0%").replace("%", "").strip()
            try:
                download_status[download_id] = {
                    "progress": float(percent_str),
                    "status": "Downloading...",
                }
            except Exception:
                pass
        elif d["status"] == "finished":
            download_status[download_id] = {"progress": 100.0, "status": "Finished"}

    ydl_opts = {
        "format": selected_format,
        "merge_output_format": "mp4",
        "outtmpl": filename,
        "progress_hooks": [progress_hook],
        "quiet": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        },
    }

    if cookie_path:
        ydl_opts["cookiefile"] = cookie_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        download_files[download_id] = filename
    except Exception as e:
        download_status[download_id] = {"progress": 0, "status": f"Error: {str(e)}"}
        if os.path.exists(filename):
            os.remove(filename)
    finally:
        if cookie_path and os.path.exists(cookie_path):
            os.remove(cookie_path)

@app.post("/download")
async def download(
    background_tasks: BackgroundTasks,
    url: str = Query(...),
    quality: str = Query("best"),
    cookiefile: UploadFile = File(None),
):
    download_id = str(uuid.uuid4())

    cookie_path = None
    if cookiefile:
        cookie_path = f"/tmp/{download_id}_cookies.txt"
        with open(cookie_path, "wb") as f:
            shutil.copyfileobj(cookiefile.file, f)

    download_status[download_id] = {"progress": 0, "status": "Queued"}

    background_tasks.add_task(download_video_task, url, quality, download_id, cookie_path)

    return {"download_id": download_id}

@app.get("/progress")
def progress(id: str = Query(...)):
    status = download_status.get(id)
    if not status:
        raise HTTPException(status_code=404, detail="Download ID not found")
    return status

@app.get("/file")
def get_file(id: str = Query(...)):
    filename = f"/tmp/{id}.mp4"
    if os.path.exists(filename):
        def iterfile():
            with open(filename, mode="rb") as file_like:
                yield from file_like
            os.remove(filename)  

        return StreamingResponse(iterfile(), media_type="video/mp4", headers={
            "Content-Disposition": f'attachment; filename="video_{id}.mp4"'
        })
    else:
        raise HTTPException(status_code=404, detail="File not found")

@app.get("/")
def home():
    return {"message": "API is running"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
