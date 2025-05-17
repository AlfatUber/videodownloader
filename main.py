from flask import Flask, request, send_file, jsonify
import yt_dlp
import os
import uuid

app = Flask(__name__)
download_status = {}

@app.get("/")
def home():
    return {"type": "success", "message": "Welcome on downloader API"}

@app.get('/progress')
def get_progress():
    download_id = request.args.get('id')
    if not download_id or download_id not in download_status:
        return jsonify({'progress': 0, 'status': 'Initializing'}), 200
    return jsonify(download_status[download_id]), 200

@app.get('/download')
def download():
    url = request.args.get('url')
    quality = request.args.get('quality', 'best')
    download_id = request.args.get('id') or str(uuid.uuid4())

    if not url:
        return jsonify({'error': 'URL is required'}), 400

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

    selected_format = format_map.get(quality.lower(), 'best')

    def progress_hook(d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '0%').replace('%', '').strip()
            try:
                download_status[download_id] = {
                    'progress': float(percent),
                    'status': 'Downloading...'
                }
            except ValueError:
                pass
        elif d['status'] == 'finished':
            download_status[download_id] = {
                'progress': 100.0,
                'status': 'Processing...'
            }

    ydl_opts = {
        'format': selected_format,
        'merge_output_format': 'mp4',
        'outtmpl': filename,
        'progress_hooks': [progress_hook],
        'quiet': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return send_file(filename, as_attachment=True, download_name="video.mp4")
    finally:
        if os.path.exists(filename):
            os.remove(filename)
        if download_id in download_status:
            del download_status[download_id]

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
