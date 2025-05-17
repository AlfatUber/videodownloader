from flask import Flask, request, send_file, after_this_request
import yt_dlp
import os
import uuid

app = Flask(__name__)

@app.get('/')
def home():
    return {"type": "success", "message": "Welcome on downloader API"}

@app.get('/download')
def download():
    url = request.args.get('url')
    quality = request.args.get('quality', 'best')  
    
    if not url:
        return {"error": "URL is required"}, 400

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

        @after_this_request
        def cleanup(response):
            try:
                if os.path.exists(filename):
                    os.remove(filename)
            except Exception as e:
                app.logger.error(f"Error deleting file: {e}")
            return response

        return send_file(filename, as_attachment=True)

    except Exception as e:
        return {"error": str(e)}, 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
