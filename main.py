from flask import Flask, request, send_file
import yt_dlp
import os
import uuid

app = Flask(__name__)


@app.get('/download')
def download():
    url = request.args.get('url')
    quality = request.args.get('quality', 'best')  
    
    if not url:
        return "URL manquante", 400

    filename = f"/tmp/{uuid.uuid4()}.mp4"

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

    ydl_opts = {
        'format': selected_format,
        'merge_output_format': 'mp4',
        'outtmpl': filename,
        'quiet': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return send_file(filename, as_attachment=True)
    finally:
        if os.path.exists(filename):
            os.remove(filename)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
