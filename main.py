import uvicorn
from fastapi import FastAPI, Query, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import os
import uuid
import shutil
import glob
import time
import subprocess

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

format_map = {
    "audio": "bestaudio[ext=m4a]/bestaudio",
    "video": "bestvideo[ext=mp4]/bestvideo",
    "audio+video": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best",
    "360p": "bestvideo[ext=mp4][height<=360]+bestaudio[ext=m4a]/best[height<=360]",
    "480p": "bestvideo[ext=mp4][height<=480]+bestaudio[ext=m4a]/best[height<=480]",
    "720p": "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[height<=720]",
    "1080p": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[height<=1080]",
    "1440p": "bestvideo[ext=mp4][height<=1440]+bestaudio[ext=m4a]/best[height<=1440]",
    "2160p": "bestvideo[ext=mp4][height<=2160]+bestaudio[ext=m4a]/best[height<=2160]",
}

def download_video_task(url, quality, download_id, cookie_path=None):
    filename = f"/tmp/{download_id}.mp4"
    selected_format = format_map.get(quality.lower(), "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best")

    def progress_hook(d):
        if d["status"] == "downloading":
            percent_str = d.get("_percent_str", "0%").replace("%", "").strip()
            download_status[download_id] = {
                "progress": float(percent_str),
                "status": "Downloading...",
            }
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
        "verbose": True,
    }

    if cookie_path:
        ydl_opts["cookiefile"] = cookie_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
        download_files[download_id] = filename
    except Exception as e:
        download_status[download_id] = {"progress": 0, "status": f"Error: {str(e)}"}
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
        if not cookiefile.filename.endswith(".txt"):
            raise HTTPException(status_code=400, detail="Le fichier cookie doit être un fichier .txt.")
        contents = await cookiefile.read()
        if len(contents) > 100 * 1024:
            raise HTTPException(status_code=400, detail="Le fichier cookie est trop volumineux (max 100 Ko).")
        cookie_path = f"/tmp/{download_id}_cookies.txt"
        with open(cookie_path, "wb") as f:
            f.write(contents)

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
    matches = glob.glob(f"/tmp/{id}.*")
    if matches:
        file_path = matches[0]
        return FileResponse(path=file_path, filename=os.path.basename(file_path), media_type="video/mp4")
    else:
        raise HTTPException(status_code=404, detail="File not found")

@app.get("/list")
def list_downloads():
    files = glob.glob("/tmp/*.mp4")
    file_info = []
    for f in files:
        file_info.append({
            "filename": os.path.basename(f),
            "size_MB": round(os.path.getsize(f) / 1024 / 1024, 2),
            "created": time.ctime(os.path.getctime(f))
        })
    return file_info

@app.get("/delete/{filename}")
def delete(filename: str):
    matches = glob.glob(f"/tmp/{filename}")
    if matches:
        os.remove(matches[0])
        return {"type": "success", "message": f"File '{filename}' deleted."}
    else:
        raise HTTPException(status_code=404, detail="File not found")

@app.get("/delete_all")
def delete_all_files():
    deleted = []
    for f in glob.glob("/tmp/*.mp4"):
        if os.path.isfile(f):
            os.remove(f)
            deleted.append(os.path.basename(f))
    return {"deleted_files": deleted}

@app.get("/supported_sites")
def supported_sites():
    try:
        result = subprocess.run(
            ["yt-dlp", "--list-extractors"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        extractors = result.stdout.strip().split("\n")
        return {"supported_sites": extractors}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du listing : {e.stderr}")

@app.post("/get_data")
async def get_video_data(url: str = Query(...), cookiefile: UploadFile = File(None)):
    cookie_path = None

    if cookiefile:
        if not cookiefile.filename.endswith(".txt"):
            raise HTTPException(status_code=400, detail="Le fichier cookie doit être un fichier .txt.")
        contents = await cookiefile.read()
        if len(contents) > 100 * 1024:
            raise HTTPException(status_code=400, detail="Le fichier cookie est trop volumineux (max 100 Ko).")
        cookie_path = f"/tmp/{uuid.uuid4()}_cookies.txt"
        with open(cookie_path, "wb") as f:
            f.write(contents)

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0"
        },
    }
    if cookie_path:
        ydl_opts["cookiefile"] = cookie_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            preview_url = next(
                (thumb.get("url") for thumb in info.get("thumbnails", []) 
                 if "webp" in thumb.get("url", "") or "preview" in thumb.get("id", "")),
                info.get("thumbnail")
            )

            return {
                "id": info.get("id"),
                "title": info.get("title"),
                "description": info.get("description"),
                "duration": info.get("duration"),
                "uploader": info.get("uploader"),
                "upload_date": info.get("upload_date"),
                "thumbnail": info.get("thumbnail"),
                "view_count": info.get("view_count"),
                "like_count": info.get("like_count"),
                "formats": [f.get("format") for f in info.get("formats", [])],
                "webpage_url": info.get("webpage_url"),
                "preview": preview_url
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'extraction : {str(e)}")

    finally:
        if cookie_path and os.path.exists(cookie_path):
            os.remove(cookie_path)

@app.get("/")
def home():
    return {"message": "API is running"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
