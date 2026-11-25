#!/usr/bin/env python3
"""
NYCTUS - Worker de notebook/PC (procesar_video.py).

Funciones:
1. Consulta videos pendientes en Render.
2. Descarga el video y confirma que el worker lo tomó.
3. Procesa los frames con YOLOv8 y tracking.
4. Guarda las detecciones en JSON.
5. Genera el video anotado y lo comprime con FFmpeg.
6. Sube el resultado a Render.
7. Informa estados, progreso y errores.
8. Envía heartbeat para informar que la PC está conectada.

IMPORTANTE:
El heartbeat NO modifica el estado del análisis.
La computadora puede estar conectada y esperando sin bloquear
el botón "Nuevo análisis" de la aplicación.
"""

import json
import os
import subprocess
import threading
import time
from datetime import datetime

import cv2
import requests
from ultralytics import YOLO


# ============================================================
# CONFIGURACIÓN
# ============================================================

API_URL = "http://127.0.0.1:8000"

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODELO_PATH = os.path.join(_BASE_DIR, "best.pt")

CARPETA_DESCARGAS = os.path.join(_BASE_DIR, "videos", "pendientes")
CARPETA_PROCESADOS = os.path.join(_BASE_DIR, "videos", "procesados")
CARPETA_LABELS = os.path.join(_BASE_DIR, "labels")

POLL_SECONDS = 10
HEARTBEAT_SECONDS = 10

MOSTRAR_VENTANA = True

os.makedirs(CARPETA_DESCARGAS, exist_ok=True)
os.makedirs(CARPETA_PROCESADOS, exist_ok=True)
os.makedirs(CARPETA_LABELS, exist_ok=True)


# ============================================================
# CARGA DEL MODELO
# ============================================================

print("[NYCTUS] Cargando modelo YOLO...")

modelo = YOLO(MODELO_PATH)

print("[NYCTUS] Modelo cargado correctamente.")


# ============================================================
# COMUNICACIÓN DE ESTADOS CON RENDER
# ============================================================

def reportar_estado(estado, progreso, mensaje):

    datos = {
        "estado": estado,
        "progreso": int(max(0, min(100, progreso))),
        "mensaje": mensaje,
    }

    try:

        respuesta = requests.post(
            f"{API_URL}/estado/actualizar",
            json=datos,
            timeout=10,
        )

        respuesta.raise_for_status()

        print(
            f"[NYCTUS] Estado: {estado} "
            f"({datos['progreso']}%) - {mensaje}"
        )

    except requests.exceptions.RequestException as e:

        print(
            f"[NYCTUS] No se pudo actualizar el estado: {e}"
        )


def informar_error(mensaje):

    print(f"[NYCTUS] ERROR: {mensaje}")

    try:

        respuesta = requests.post(
            f"{API_URL}/estado/error",
            json={"error": str(mensaje)},
            timeout=10,
        )

        respuesta.raise_for_status()

    except requests.exceptions.RequestException as e:

        print(
            f"[NYCTUS] No se pudo informar el error: {e}"
        )


# ============================================================
# HEARTBEAT DEL WORKER
# ============================================================

def mantener_worker_activo():

    """
    Envía señales periódicas a Render.

    IMPORTANTE:
    Este proceso solamente informa que la PC está conectada.
    No modifica el estado del análisis.
    """

    while True:

        try:

            respuesta = requests.post(
                f"{API_URL}/worker/heartbeat",
                timeout=10,
            )

            respuesta.raise_for_status()

        except requests.exceptions.RequestException as e:

            print(
                f"[NYCTUS] Heartbeat: no se pudo contactar Render: {e}"
            )

        time.sleep(HEARTBEAT_SECONDS)


def iniciar_heartbeat():

    hilo = threading.Thread(
        target=mantener_worker_activo,
        daemon=True,
    )

    hilo.start()

    print("[NYCTUS] Heartbeat iniciado.")


# ============================================================
# COMPRESIÓN CON FFMPEG
# ============================================================

def comprimir_video(entrada, salida):

    reportar_estado(
        "comprimiendo",
        88,
        "Comprimiendo el video para la aplicación...",
    )

    print("\n[NYCTUS] Comprimiendo video...")

    comando = [
        "ffmpeg",
        "-y",
        "-i", entrada,
        "-vf", "scale=1280:720",
        "-r", "30",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "27",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        salida,
    ]

    subprocess.run(
        comando,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )

    print("[NYCTUS] Video comprimido correctamente.")

    reportar_estado(
        "comprimiendo",
        93,
        "Compresión finalizada.",
    )


# ============================================================
# PROCESAMIENTO DE UN VIDEO CON YOLO
# ============================================================

def procesar_video(video_entrada):

    reportar_estado(
        "procesando",
        20,
        "La inteligencia artificial está analizando el video.",
    )

    cap = cv2.VideoCapture(video_entrada)

    if not cap.isOpened():
        raise Exception("No se pudo abrir el video descargado.")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30

    ancho = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    alto = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    cantidad_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    duracion = cantidad_frames / fps if fps else 0

    nombre_video = os.path.splitext(
        os.path.basename(video_entrada)
    )[0]

    video_salida = os.path.join(
        CARPETA_PROCESADOS,
        f"{nombre_video}_procesado.mp4",
    )

    video_compacto = os.path.join(
        CARPETA_PROCESADOS,
        f"{nombre_video}_720p.mp4",
    )

    labels_salida = os.path.join(
        CARPETA_LABELS,
        f"{nombre_video}_labels.json",
    )

    writer = cv2.VideoWriter(
        video_salida,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (ancho, alto),
    )

    if not writer.isOpened():

        cap.release()

        raise Exception("No se pudo crear el video de salida.")

    ids_unicos = set()
    detecciones = []

    frame_numero = 0
    ultimo_reporte = 0

    print("\n========================================")
    print("INICIANDO PROCESAMIENTO")
    print("========================================")

    try:

        while cap.isOpened():

            ret, frame = cap.read()

            if not ret:
                break

            frame_numero += 1

            # --------------------------------------------
            # DETECCIÓN Y TRACKING YOLO
            # --------------------------------------------

            resultados = modelo.track(
                frame,
                conf=0.5,
                persist=True,
                verbose=False,
            )[0]

            if resultados.boxes.id is not None:

                ids_unicos.update(
                    resultados.boxes.id.int().tolist()
                )

            en_frame = len(resultados.boxes)

            # --------------------------------------------
            # GUARDADO DE DETECCIONES
            # --------------------------------------------

            if resultados.boxes is not None:

                cajas = resultados.boxes

                for i in range(len(cajas)):

                    tracking_id = (
                        int(cajas.id[i].item())
                        if cajas.id is not None
                        else None
                    )

                    clase_id = int(cajas.cls[i].item())

                    nombre_clase = modelo.names[clase_id]

                    confianza = float(cajas.conf[i].item())

                    x1, y1, x2, y2 = cajas.xyxy[i].tolist()

                    detecciones.append({
                        "frame": frame_numero,
                        "tracking_id": tracking_id,
                        "clase": nombre_clase,
                        "confianza": confianza,
                        "x1": float(x1),
                        "y1": float(y1),
                        "x2": float(x2),
                        "y2": float(y2),
                    })

            # --------------------------------------------
            # VIDEO ANOTADO
            # --------------------------------------------

            frame_anotado = resultados.plot()

            if frame_anotado.shape[:2] != (alto, ancho):

                frame_anotado = cv2.resize(
                    frame_anotado,
                    (ancho, alto),
                    interpolation=cv2.INTER_LINEAR,
                )

            cv2.rectangle(
                frame_anotado,
                (10, 10),
                (380, 80),
                (0, 0, 0),
                -1,
            )

            cv2.putText(
                frame_anotado,
                f"En escena: {en_frame}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 255, 80),
                2,
            )

            cv2.putText(
                frame_anotado,
                f"Total unicas: {len(ids_unicos)}",
                (20, 72),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 200, 255),
                2,
            )

            writer.write(frame_anotado)

            # --------------------------------------------
            # PROGRESO DEL PROCESAMIENTO
            # --------------------------------------------

            if cantidad_frames > 0:

                progreso = 20 + int(
                    (frame_numero / cantidad_frames) * 65
                )

                progreso = min(progreso, 85)

                if progreso != ultimo_reporte:

                    reportar_estado(
                        "procesando",
                        progreso,
                        f"Analizando video: {frame_numero} "
                        f"de {cantidad_frames} frames.",
                    )

                    ultimo_reporte = progreso

            # --------------------------------------------
            # VENTANA DE PREVISUALIZACIÓN
            # --------------------------------------------

            if MOSTRAR_VENTANA:

                cv2.imshow(
                    "NYCTUS - IA",
                    frame_anotado,
                )

                if cv2.waitKey(1) & 0xFF == 27:

                    raise Exception(
                        "Procesamiento interrumpido por el usuario."
                    )

    finally:

        cap.release()
        writer.release()

        if MOSTRAR_VENTANA:
            cv2.destroyAllWindows()

    # --------------------------------------------
    # COMPRESIÓN
    # --------------------------------------------

    comprimir_video(
        video_salida,
        video_compacto,
    )

    if os.path.exists(video_salida):
        os.remove(video_salida)

    # --------------------------------------------
    # GUARDADO DE LABELS JSON
    # --------------------------------------------

    total_ganado = len(ids_unicos)

    datos_labels = {
        "video": os.path.basename(video_compacto),
        "fecha": datetime.now().isoformat(),
        "duracion_segundos": duracion,
        "total_ganado": total_ganado,
        "detecciones": detecciones,
    }

    with open(
        labels_salida,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            datos_labels,
            f,
            indent=4,
            ensure_ascii=False,
        )

    print("\n========================================")
    print("PROCESAMIENTO TERMINADO")
    print("========================================")

    print(f"Ganado detectado: {total_ganado}")
    print(f"Duración: {duracion:.2f} segundos")
    print(f"Video procesado: {video_compacto}")
    print(f"Labels guardados: {labels_salida}")

    return {
        "video_path": video_compacto,
        "ganado": total_ganado,
        "duracion": duracion,
    }


# ============================================================
# COMUNICACIÓN CON RENDER
# ============================================================

def hay_video_pendiente():

    try:

        respuesta = requests.get(
            f"{API_URL}/video-pendiente",
            timeout=15,
        )

        respuesta.raise_for_status()

        datos = respuesta.json()

        return datos.get("estado") == "disponible"

    except requests.exceptions.RequestException as e:

        print(
            f"[NYCTUS] Error consultando videos pendientes: {e}"
        )

        return False


def descargar_video():

    destino = os.path.join(
        CARPETA_DESCARGAS,
        f"nyctus_{int(time.time())}.mp4",
    )

    print("[NYCTUS] Descargando video desde Render...")

    respuesta = requests.get(
        f"{API_URL}/descargar-video",
        timeout=(15, 180),
        stream=True,
    )

    respuesta.raise_for_status()

    try:

        with open(destino, "wb") as f:

            for bloque in respuesta.iter_content(
                chunk_size=1024 * 1024
            ):

                if bloque:
                    f.write(bloque)

    except Exception:

        if os.path.exists(destino):
            os.remove(destino)

        raise

    finally:

        respuesta.close()

    if not os.path.exists(destino) or os.path.getsize(destino) == 0:

        raise Exception("El video descargado está vacío.")

    print(f"[NYCTUS] Video descargado: {destino}")

    # Confirmamos que el worker tomó el video.

    confirmacion = requests.post(
        f"{API_URL}/video-pendiente/confirmar",
        timeout=15,
    )

    confirmacion.raise_for_status()

    print("[NYCTUS] Video confirmado en Render.")

    return destino


def subir_resultado(resultado):

    reportar_estado(
        "subiendo_resultado",
        95,
        "Subiendo el video procesado a la nube.",
    )

    datos = {
        "ganado": str(resultado["ganado"]),
        "personas": "0",
        "duracion": str(resultado["duracion"]),
        "fecha": datetime.now().isoformat(),
    }

    ruta_video = resultado["video_path"]

    print("[NYCTUS] Subiendo resultado a Render...")

    with open(ruta_video, "rb") as f:

        respuesta = requests.post(
            f"{API_URL}/subir-analisis",
            data=datos,
            files={
                "file": (
                    os.path.basename(ruta_video),
                    f,
                    "video/mp4",
                )
            },
            timeout=(20, 600),
        )

    respuesta.raise_for_status()

    print(
        f"[NYCTUS] Resultado subido correctamente: "
        f"{respuesta.status_code}"
    )

    print(f"[NYCTUS] Respuesta: {respuesta.text[:300]}")

    return True


# ============================================================
# LOOP PRINCIPAL
# ============================================================

def main():

    print("\n========================================")
    print("NYCTUS - WORKER DE INTELIGENCIA ARTIFICIAL")
    print("========================================")

    print(f"Servidor: {API_URL}")
    print(f"Intervalo de consulta: {POLL_SECONDS} segundos")

    iniciar_heartbeat()

    # IMPORTANTE:
    # No enviar "esperando_ia" al iniciar.
    # El worker está conectado, pero eso no significa que
    # exista un análisis en curso.
    print(
        "[NYCTUS] Worker conectado. "
        "Esperando videos sin modificar el estado del análisis."
    )

    while True:

        try:

            if hay_video_pendiente():

                print("\n[NYCTUS] Se encontró un video pendiente.")

                try:

                    reportar_estado(
                        "descargando",
                        15,
                        "Descargando video desde Raspberry Pi.",
                    )

                    video_local = descargar_video()

                    resultado = procesar_video(video_local)

                    if resultado is None:

                        raise Exception(
                            "El procesamiento no devolvió resultados."
                        )

                    subir_resultado(resultado)

                    print(
                        "\n[NYCTUS] Análisis enviado correctamente."
                    )

                except Exception as e:

                    informar_error(str(e))

                    print(
                        f"[NYCTUS] Error durante el análisis: {e}"
                    )

            else:

                time.sleep(POLL_SECONDS)

        except KeyboardInterrupt:

            print("\n[NYCTUS] Worker detenido manualmente.")

            break

        except Exception as e:

            print(f"[NYCTUS] Error en el loop principal: {e}")

            time.sleep(POLL_SECONDS)


# ============================================================
# INICIO
# ============================================================

if __name__ == "__main__":
    main()