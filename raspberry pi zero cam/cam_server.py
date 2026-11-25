
import os
import shutil
import signal
import subprocess
import threading
import time
import json
import socket

import requests
from flask import Flask, redirect, request, send_from_directory


# ============================================================
# CONFIGURACIÓN
# ============================================================

AUTO_START = False

WIFI_OFF_MINUTES = 0
WIFI_IFACE = "wlan0"
WAIT_FOR_WIFI_SECONDS = 40

HOTSPOT_NAME = "PiCamHotspot"
HOTSPOT_SSID = "PiCam"
HOTSPOT_PASS = os.environ.get("HOTSPOT_PASS", "picam1234")

DIR = os.environ.get("VIDEO_DIR", "/home/nyctus/videos")
NAME_FORMAT = "%Y-%m-%d_%H-%M-%S"

RENDER_POLL_SECONDS = int(
    os.environ.get("RENDER_POLL_SECONDS", "5")
)

AUTO_RECORD_SECONDS = int(
    os.environ.get("AUTO_RECORD_SECONDS", "40")
)


# ============================================================
# NYCTUS - DESCUBRIMIENTO AUTOMÁTICO DEL SERVIDOR
# ============================================================

API_URL = None

PUERTO_DESCUBRIMIENTO = 37020
MENSAJE_DESCUBRIMIENTO = b"NYCTUS_DISCOVER"


def descubrir_servidor(timeout=4):
    global API_URL

    cliente = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM
    )

    cliente.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_BROADCAST,
        1
    )

    cliente.settimeout(timeout)

    try:
        print("[NYCTUS] Buscando servidor en la red local...")

        cliente.sendto(
            MENSAJE_DESCUBRIMIENTO,
            ("255.255.255.255", PUERTO_DESCUBRIMIENTO)
        )

        while True:
            datos, direccion = cliente.recvfrom(1024)

            try:
                respuesta = json.loads(
                    datos.decode("utf-8")
                )

                if respuesta.get("service") != "nyctus":
                    continue

                host = respuesta.get("host")
                puerto = respuesta.get("port")

                if host and puerto:
                    API_URL = f"http://{host}:{puerto}"

                    print(
                        f"[NYCTUS] Servidor encontrado: {API_URL}"
                    )

                    return API_URL

            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

    except socket.timeout:
        print(
            "[NYCTUS] No se encontró el servidor. "
            "Se volverá a intentar."
        )

    except Exception as error:
        print(
            f"[NYCTUS] Error durante el descubrimiento: {error}"
        )

    finally:
        cliente.close()

    return None


def obtener_api_url():
    global API_URL

    if API_URL:
        return API_URL

    return descubrir_servidor()


def reiniciar_archivos(kwargs):
    """
    Vuelve al inicio los archivos abiertos para que una segunda
    petición pueda reenviarlos si se perdió la conexión.
    """

    archivos = kwargs.get("files")

    if not isinstance(archivos, dict):
        return

    for valor in archivos.values():
        if isinstance(valor, (tuple, list)) and len(valor) >= 2:
            archivo = valor[1]

            if hasattr(archivo, "seek"):
                try:
                    archivo.seek(0)
                except Exception:
                    pass


def api_request(metodo, endpoint, **kwargs):
    """
    Envía solicitudes a FastAPI.

    Si se pierde la conexión:
    1. Descarta la IP anterior.
    2. Busca nuevamente el servidor.
    3. Reintenta la solicitud.
    """

    global API_URL

    url = obtener_api_url()

    if not url:
        raise ConnectionError(
            "No se encontró el servidor NYCTUS"
        )

    try:
        return requests.request(
            metodo,
            url + endpoint,
            **kwargs
        )

    except requests.RequestException:
        print(
            "[NYCTUS] Conexión perdida. "
            "Buscando nuevamente el servidor..."
        )

        API_URL = None

        reiniciar_archivos(kwargs)

        url = descubrir_servidor()

        if not url:
            raise ConnectionError(
                "No se pudo recuperar la conexión con NYCTUS"
            )

        print("[NYCTUS] Reintentando solicitud...")

        return requests.request(
            metodo,
            url + endpoint,
            **kwargs
        )


# ============================================================
# INICIALIZACIÓN DE FLASK
# ============================================================

app = Flask(__name__)

os.makedirs(DIR, exist_ok=True)

proc = None
current = None
started_mono = None

auto_analysis_lock = threading.Lock()


# ============================================================
# PÁGINA WEB
# ============================================================

PAGE = """<!doctype html>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pi Camera</title>
<body style="font-family:sans-serif;max-width:480px;margin:2em auto;padding:0 1em">
<h2>Pi Camera</h2>
<p><b>{status}</b><br><small>Pi clock: <span id="clock">{clock}</span></small></p>
<form method="post" action="/start" style="display:inline">
  <button style="font-size:1.4em;padding:.6em 1em">Start</button>
</form>
<form method="post" action="/stop" style="display:inline">
  <button style="font-size:1.4em;padding:.6em 1em">Stop</button>
</form>
<h3>Videos</h3>
<ul>{files}</ul>
<script>
fetch('/settime', {method: 'POST', body: String(Date.now())})
  .then(function (r) { return r.text(); })
  .then(function (t) { document.getElementById('clock').textContent = t; })
  .catch(function () {});
</script>
</body>
"""


# ============================================================
# COMUNICACIÓN CON NYCTUS
# ============================================================

def reportar_estado(
    estado,
    progreso=None,
    mensaje=None,
    error=None
):
    datos = {
        "estado": estado,
        "mensaje": mensaje or estado
    }

    if progreso is not None:
        datos["progreso"] = progreso

    if error is not None:
        datos["error"] = error

    try:
        respuesta = api_request(
            "POST",
            "/estado/actualizar",
            json=datos,
            timeout=10
        )

        respuesta.raise_for_status()

        return True

    except Exception as e:
        print(
            f"[NYCTUS] No se pudo informar el estado: {e}"
        )

        return False


def informar_error(mensaje):
    try:
        respuesta = api_request(
            "POST",
            "/estado/error",
            json={
                "mensaje": mensaje,
                "error": mensaje
            },
            timeout=10
        )

        respuesta.raise_for_status()

    except Exception as e:
        print(
            f"[NYCTUS] No se pudo informar el error: {e}"
        )


# ============================================================
# WI-FI
# ============================================================

def nm(*args):
    return subprocess.run(
        ["nmcli", *args],
        capture_output=True,
        text=True
    )


def wifi_connected():
    out = nm(
        "-t",
        "-f",
        "DEVICE,STATE,CONNECTION",
        "device"
    ).stdout

    for line in out.splitlines():
        parts = (line.split(":") + ["", "", ""])[:3]

        device, state, connection = parts

        if device == WIFI_IFACE and state == "connected":
            return connection != HOTSPOT_NAME

    return False


def start_hotspot():
    print("[NYCTUS] No se encontró Wi-Fi. Creando hotspot propio...")

    nm("connection", "delete", HOTSPOT_NAME)

    nm(
        "device",
        "wifi",
        "hotspot",
        "ifname",
        WIFI_IFACE,
        "con-name",
        HOTSPOT_NAME,
        "ssid",
        HOTSPOT_SSID,
        "password",
        HOTSPOT_PASS
    )

    nm(
        "connection",
        "modify",
        HOTSPOT_NAME,
        "connection.autoconnect",
        "no"
    )


def ensure_network():
    print("[NYCTUS] Comprobando conexión Wi-Fi...")

    nm("radio", "wifi", "on")

    deadline = time.time() + WAIT_FOR_WIFI_SECONDS

    while time.time() < deadline:

        if wifi_connected():
            print("[NYCTUS] Conexión Wi-Fi establecida.")
            return

        time.sleep(2)

    start_hotspot()


# ============================================================
# RELOJ
# ============================================================

def now_text():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def clock_synced():
    out = subprocess.run(
        [
            "timedatectl",
            "show",
            "-p",
            "NTPSynchronized",
            "--value"
        ],
        capture_output=True,
        text=True
    ).stdout.strip()

    return out == "yes"


# ============================================================
# GRABACIÓN
# ============================================================

def recording():
    return proc is not None and proc.poll() is None


def start_recording():
    global proc, current, started_mono

    if recording():
        return False

    started_mono = time.monotonic()

    current = os.path.join(
        DIR,
        time.strftime("rec_%Y%m%d_%H%M%S")
    )

    try:
        proc = subprocess.Popen([
            "rpicam-vid",
            "-t", "0",
            "-n",
            "--width", "1920",
            "--height", "1080",
            "--framerate", "30",
            "--bitrate", "20000000",
            "-o", current + ".h264"
        ])

        print("[CAMERA] Grabación iniciada.")

        return True

    except Exception as e:
        print(
            f"[CAMERA] Error al iniciar grabación: {e}"
        )

        proc = None
        current = None
        started_mono = None

        return False


def stop_recording():
    """
    Detiene la grabación y devuelve el MP4 final.
    Si FFmpeg no está disponible, devuelve el H264.
    """

    global proc, current, started_mono

    if not recording():
        return None

    elapsed = time.monotonic() - started_mono
    began = time.time() - elapsed

    proceso_actual = proc
    archivo_actual = current

    proceso_actual.send_signal(signal.SIGINT)
    proceso_actual.wait()

    proc = None

    final = os.path.join(
        DIR,
        time.strftime(
            NAME_FORMAT,
            time.localtime(began)
        )
    )

    n = 1
    base = final

    while (
        os.path.exists(base + ".h264")
        or os.path.exists(base + ".mp4")
    ):
        n += 1
        base = f"{final}_{n}"

    archivo_h264 = archivo_actual + ".h264"
    archivo_final_h264 = base + ".h264"

    if not os.path.exists(archivo_h264):
        return None

    os.rename(
        archivo_h264,
        archivo_final_h264
    )

    if shutil.which("ffmpeg"):

        resultado = subprocess.run([
            "ffmpeg",
            "-y",
            "-r", "30",
            "-i", archivo_final_h264,
            "-c", "copy",
            base + ".mp4"
        ])

        if (
            resultado.returncode == 0
            and os.path.exists(base + ".mp4")
        ):
            os.remove(archivo_final_h264)

            current = None
            started_mono = None

            print("[CAMERA] Video convertido a MP4.")

            return base + ".mp4"

    current = None
    started_mono = None

    print("[CAMERA] No se pudo convertir a MP4.")

    return archivo_final_h264


# ============================================================
# PÁGINA WEB MANUAL
# ============================================================

@app.route("/")
def home():
    names = sorted(
        os.listdir(DIR),
        reverse=True
    )

    items = "".join(
        f'<li><a href="/video/{n}">{n}</a></li>'
        for n in names
        if n.endswith((".mp4", ".h264"))
    )

    status = (
        "Recording..."
        if recording()
        else "Idle"
    )

    return (
        PAGE.replace("{status}", status)
        .replace("{clock}", now_text())
        .replace("{files}", items or "<li>none yet</li>")
    )


@app.route("/settime", methods=["POST"])
def settime():
    try:
        phone = int(
            request.get_data(as_text=True)
        ) / 1000.0

    except ValueError:
        return "bad time", 400

    if (
        phone > 1.7e9
        and not clock_synced()
        and abs(phone - time.time()) > 2
    ):
        subprocess.run([
            "date",
            "-s",
            f"@{int(phone)}"
        ])

    return now_text()


@app.route("/start", methods=["POST"])
def start():
    start_recording()
    return redirect("/")


@app.route("/stop", methods=["POST"])
def stop():
    stop_recording()
    return redirect("/")


@app.route("/video/<name>")
def video(name):
    return send_from_directory(
        DIR,
        name,
        as_attachment=True
    )


# ============================================================
# ANÁLISIS AUTOMÁTICO SOLICITADO DESDE FLUTTER
# ============================================================

def run_auto_analysis():
    """
    Flujo:
    1. Comprueba que la cámara esté libre.
    2. Informa que comienza la grabación.
    3. Graba AUTO_RECORD_SECONDS.
    4. Informa que está subiendo el video.
    5. Envía el video original a la PC.
    6. Confirma la orden solamente si la subida fue exitosa.
    """

    if not auto_analysis_lock.acquire(blocking=False):
        return

    try:

        if recording():
            print(
                "[NYCTUS] Cámara ocupada por grabación manual."
            )
            return

        print(
            f"[NYCTUS] Comenzando grabación automática "
            f"de {AUTO_RECORD_SECONDS} segundos."
        )

        reportar_estado(
            "grabando",
            5,
            "La Raspberry Pi está grabando el video"
        )

        if not start_recording():
            informar_error(
                "No se pudo iniciar la cámara"
            )
            return

        time.sleep(AUTO_RECORD_SECONDS)

        video_path = stop_recording()

        if (
            not video_path
            or not os.path.exists(video_path)
        ):
            informar_error(
                "La grabación terminó sin generar un archivo"
            )
            return

        print(
            f"[NYCTUS] Video grabado: {video_path}"
        )

        reportar_estado(
            "subiendo",
            12,
            "La Raspberry Pi está enviando el video al servidor"
        )

        try:

            with open(video_path, "rb") as f:

                nombre = os.path.basename(video_path)

                tipo_video = (
                    "video/mp4"
                    if video_path.endswith(".mp4")
                    else "video/x-h264"
                )

                respuesta = api_request(
                    "POST",
                    "/subir-video",
                    files={
                        "file": (
                            nombre,
                            f,
                            tipo_video
                        )
                    },
                    timeout=180
                )

            respuesta.raise_for_status()

            confirmacion = api_request(
                "POST",
                "/pendientes/confirmar",
                timeout=15
            )

            confirmacion.raise_for_status()

            print(
                f"[NYCTUS] Video enviado correctamente: {video_path}"
            )

        except Exception as e:

            print(
                f"[NYCTUS] Error subiendo video: {e}"
            )

            informar_error(
                "La Raspberry no pudo enviar el video al servidor: "
                + str(e)
            )

    except Exception as e:

        print(
            f"[NYCTUS] Error en análisis automático: {e}"
        )

        informar_error(str(e))

    finally:
        auto_analysis_lock.release()


# ============================================================
# CONSULTAR ÓRDENES DE NYCTUS
# ============================================================

def poll_render():
    print(
        "[NYCTUS] Iniciando búsqueda automática del servidor..."
    )

    while True:

        try:

            respuesta = api_request(
                "GET",
                "/pendientes",
                timeout=10
            )

            respuesta.raise_for_status()

            datos = respuesta.json()

            if datos.get("accion") == "analizar":

                if (
                    not recording()
                    and not auto_analysis_lock.locked()
                ):
                    run_auto_analysis()

        except Exception as e:

            print(
                f"[NYCTUS] Error consultando el servidor: {e}"
            )

        time.sleep(RENDER_POLL_SECONDS)


# ============================================================
# INICIO DEL SISTEMA
# ============================================================

if __name__ == "__main__":

    print("========================================")
    print("       NYCTUS - RASPBERRY PI")
    print("========================================")

    if AUTO_START:
        start_recording()

    if WIFI_OFF_MINUTES > 0:

        nm("radio", "wifi", "off")

        worker_thread = threading.Timer(
            WIFI_OFF_MINUTES * 60,
            ensure_network
        )

    else:

        worker_thread = threading.Thread(
            target=ensure_network,
            daemon=True
        )

    worker_thread.daemon = True
    worker_thread.start()

    # Inicia el polling aunque todavía no se haya descubierto la PC.
    poll_thread = threading.Thread(
        target=poll_render,
        daemon=True
    )

    poll_thread.start()

    print("[NYCTUS] Sistema iniciado.")
    print("[NYCTUS] Página de cámara disponible en el puerto 80.")

    app.run(
        host="0.0.0.0",
        port=80,
        threaded=True
    )
