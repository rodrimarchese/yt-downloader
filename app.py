import os
import uuid
import threading
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, jsonify
from yt_dlp import YoutubeDL

app = Flask(__name__)
app.secret_key = 'clave-secreta-para-flash'  # Cámbiala en producción

# Carpeta donde se guardan los videos descargados
DOWNLOAD_FOLDER = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Diccionario global para monitorear progreso de descargas
# Estructura: download_progress[job_id] = {
#     "status": "downloading"|"finished"|"error",
#     "progress": 0..100,
#     "filename": None,
#     "error": None
# }
download_progress = {}

def run_download(job_id, video_url, selected_format):
    """
    Función en un hilo separado que descarga el video con yt-dlp
    y actualiza el progreso en `download_progress`.
    """
    unique_name = str(uuid.uuid4())
    output_path = os.path.join(DOWNLOAD_FOLDER, f"{unique_name}.%(ext)s")

    def progress_hook(d):
        """Se llama mientras yt-dlp descarga fragmentos. Actualiza el progreso."""
        if d['status'] == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            if total_bytes:
                porcentaje = (d['downloaded_bytes'] / total_bytes) * 100
            else:
                porcentaje = 0.0

            download_progress[job_id]['progress'] = round(porcentaje, 2)
            download_progress[job_id]['status'] = 'downloading'

        elif d['status'] == 'finished':
            download_progress[job_id]['progress'] = 100.0
            download_progress[job_id]['status'] = 'finished'

    ydl_opts = {
        'format': selected_format,
        'outtmpl': output_path,
        'merge_output_format': 'mp4',
        'noprogress': True,
        'quiet': True,
        'progress_hooks': [progress_hook],
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            final_file = ydl.prepare_filename(info)

            # Aseguramos extensión .mp4 si no la añadió
            if os.path.splitext(final_file)[1] == '':
                final_file += '.mp4'

            download_progress[job_id]['filename'] = os.path.basename(final_file)
            download_progress[job_id]['status'] = 'finished'
            download_progress[job_id]['progress'] = 100.0

    except Exception as e:
        # Si ocurre un error durante la descarga
        download_progress[job_id]['status'] = 'error'
        download_progress[job_id]['error'] = str(e)
        download_progress[job_id]['progress'] = 0.0


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # 1. Obtener la URL para listar formatos
        video_url = request.form.get('video_url')
        if not video_url:
            flash('Por favor, ingresa una URL válida', 'error')
            return redirect(url_for('index'))

        # 2. Listar formatos con yt-dlp (sin descargar)
        ydl_opts = {
            'listformats': True,
            'quiet': True
        }

        formatos_disponibles = []
        video_title = "Sin título"
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                video_title = info.get('title', 'Sin título')
                formats = info.get('formats', [])
                for f in formats:
                    formatos_disponibles.append({
                        'format_id': f.get('format_id', ''),
                        'ext': f.get('ext', ''),
                        'resolution': f.get('resolution', 'audio'),
                        'acodec': f.get('acodec', ''),
                        'vcodec': f.get('vcodec', ''),
                        'format_note': f.get('format_note', ''),
                        'filesize': f.get('filesize') or 0,
                        'tbr': f.get('tbr')
                    })
        except Exception as e:
            flash(f"Error al obtener formatos: {str(e)}", 'error')
            return redirect(url_for('index'))

        return render_template('index.html', video_url=video_url, formatos=formatos_disponibles,
                                           video_title=video_title)

    # GET: página inicial sin formatos
    return render_template('index.html', video_url=None, formatos=None)


@app.route('/start_download', methods=['POST'])
def start_download():
    """
    Endpoint para iniciar la descarga en segundo plano.
    Retorna un job_id que el frontend usará para hacer polling.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data in request"}), 400

    video_url = data.get('video_url')
    selected_format = data.get('format_id')

    if not video_url or not selected_format:
        return jsonify({"error": "Faltan parámetros video_url o format_id"}), 400

    # Crear un job_id para rastrear el progreso
    job_id = str(uuid.uuid4())
    download_progress[job_id] = {
        'status': 'pending',
        'progress': 0.0,
        'filename': None,
        'error': None
    }

    # Lanzar el hilo que ejecuta la descarga
    t = threading.Thread(target=run_download, args=(job_id, video_url, selected_format))
    t.start()

    return jsonify({"job_id": job_id})


@app.route('/progress/<job_id>')
def get_progress(job_id):
    """
    Endpoint de polling para devolver el estado y avance de la descarga.
    """
    if job_id not in download_progress:
        return jsonify({"error": "Job no encontrado"}), 404

    return jsonify(download_progress[job_id])


@app.route('/downloads/<path:filename>')
def download_file(filename):
    """
    Permite descargar el archivo final una vez completado.
    """
    return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)


if __name__ == '__main__':
    # Cambia el puerto si 5000 está en uso
    app.run(debug=True, host='0.0.0.0', port=5001)
