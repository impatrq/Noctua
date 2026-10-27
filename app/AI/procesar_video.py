#!/usr/bin/env python3
"""
NYCTUS - Worker de notebook/PC (procesar_video.py).

Toma tu script de procesamiento (YOLOv8 + conteo por tracking + overlay +
compresión ffmpeg) y lo convierte en un loop que:

  1. Pregunta a Render GET /video-pendiente cada POLL_SECONDS.
  2. Si hay un video ("estado": "disponible"), lo descarga con
     GET /descargar-video y confirma con POST /video-pendiente/confirmar
     (así Render no lo vuelve a ofrecer mientras este se procesa).
  3. Corre el mismo pipeline de YOLO que ya tenías (sin cambios de lógica).
  4. Comprime el resultado con ffmpeg (igual que antes: 1280x720, CRF 27).
  5. Sube ganado/personas/duracion/fecha + el video procesado en una sola
     llamada multipart a POST /subir-analisis, que ya lo guarda y lo deja
     disponible para Flutter en GET /video-analisis/<nombre>.

Esto está ajustado al server.py real de Render (versión con
/video-pendiente/confirmar y /subir-analisis multipart).

Requisitos en esta máquina:
    pip install ultralytics opencv-python requests
    ffmpeg instalado y en el PATH
"""

import json
import os
import subprocess
import time
from datetime import datetime

import cv2
import requests
from ultralytics import YOLO

# ============================================================
# CONFIGURACIÓN
# ============================================================
API_URL = "https://nyctus.onrender.com"
MODELO_PATH = "best.pt"

CARPETA_DESCARGAS = "videos/pendientes"
CARPETA_PROCESADOS = "videos/procesados"
CARPETA_LABELS = "labels"

POLL_SECONDS = 10          # cada cuánto pregunta si hay un video nuevo
MOSTRAR_VENTANA = True      # False = corre sin abrir la ventana de preview

os.makedirs(CARPETA_DESCARGAS, exist_ok=True)
os.makedirs(CARPETA_PROCESADOS, exist_ok=True)
os.makedirs(CARPETA_LABELS, exist_ok=True)

print("Cargando modelo YOLO...")
modelo = YOLO(MODELO_PATH)
print("Modelo cargado correctamente.")


# ============================================================
# COMPRESIÓN CON FFMPEG (igual que tu script original)
# ============================================================
def comprimir_video(entrada, salida):
    print("\nComprimiendo video para la app...")
    comando = [
        "ffmpeg", "-y", "-i", entrada,
        "-vf", "scale=1280:720",
        "-r", "30",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "27",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        salida,
    ]
    subprocess.run(comando, check=True)
    print("✓ Video comprimido.")


# ============================================================
# PROCESAMIENTO DE UN VIDEO (tu mismo flujo, convertido en función)
# ============================================================
def procesar_video(video_entrada):
    cap = cv2.VideoCapture(video_entrada)
    if not cap.isOpened():
        print("ERROR: no se pudo abrir el video.")
        return None

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    ancho = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    alto = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cantidad_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duracion = cantidad_frames / fps if fps else 0

    nombre_video = os.path.splitext(os.path.basename(video_entrada))[0]
    video_salida = os.path.join(CARPETA_PROCESADOS, f"{nombre_video}_procesado.mp4")
    labels_salida = os.path.join(CARPETA_LABELS, f"{nombre_video}_labels.json")

    writer = cv2.VideoWriter(
        video_salida, cv2.VideoWriter_fourcc(*"mp4v"), fps, (ancho, alto)
    )

    ids_unicos = set()
    detecciones = []
    frame_numero = 0

    print("\n========================================")
    print("INICIANDO PROCESAMIENTO")
    print("========================================")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frame_numero += 1

        resultados = modelo.track(frame, conf=0.5, persist=True, verbose=False)[0]

        if resultados.boxes.id is not None:
            ids_unicos.update(resultados.boxes.id.int().tolist())

        en_frame = len(resultados.boxes)

        if resultados.boxes is not None:
            cajas = resultados.boxes
            for i in range(len(cajas)):
                tracking_id = int(cajas.id[i].item()) if cajas.id is not None else None
                clase_id = int(cajas.cls[i].item())
                nombre_clase = modelo.names[clase_id]
                confianza = float(cajas.conf[i].item())
                x1, y1, x2, y2 = cajas.xyxy[i].tolist()
                detecciones.append({
                    "frame": frame_numero,
                    "tracking_id": tracking_id,
                    "clase": nombre_clase,
                    "confianza": confianza,
                    "x1": float(x1), "y1": float(y1),
                    "x2": float(x2), "y2": float(y2),
                })

        frame_anotado = resultados.plot()
        if frame_anotado.shape[:2] != (alto, ancho):
            frame_anotado = cv2.resize(
                frame_anotado, (ancho, alto), interpolation=cv2.INTER_LINEAR
            )

        cv2.rectangle(frame_anotado, (10, 10), (380, 80), (0, 0, 0), -1)
        cv2.putText(frame_anotado, f"En escena: {en_frame}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 80), 2)
        cv2.putText(frame_anotado, f"Total unicas: {len(ids_unicos)}", (20, 72),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 200, 255), 2)

        writer.write(frame_anotado)

        if MOSTRAR_VENTANA:
            cv2.imshow("NYCTUS - IA", frame_anotado)
            if cv2.waitKey(1) & 0xFF == 27:
                break

    cap.release()
    writer.release()
    if MOSTRAR_VENTANA:
        cv2.destroyAllWindows()

    video_compacto = os.path.join(CARPETA_PROCESADOS, f"{nombre_video}_720p.mp4")
    comprimir_video(video_salida, video_compacto)
    os.remove(video_salida)

    total_ganado = len(ids_unicos)

    datos_labels = {
        "video": os.path.basename(video_compacto),
        "fecha": datetime.now().isoformat(),
        "duracion_segundos": duracion,
        "total_ganado": total_ganado,
        "detecciones": detecciones,
    }
    with open(labels_salida, "w", encoding="utf-8") as f:
        json.dump(datos_labels, f, indent=4, ensure_ascii=False)

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
        r = requests.get(f"{API_URL}/video-pendiente", timeout=15)
        r.raise_for_status()
        data = r.json()
        return data.get("estado") == "disponible"
    except requests.exceptions.RequestException as e:
        print(f"[nyctus] error consultando /video-pendiente: {e}")
        return False


def descargar_video():
    destino = os.path.join(CARPETA_DESCARGAS, f"nyctus_{int(time.time())}.mp4")
    r = requests.get(f"{API_URL}/descargar-video", timeout=60)
    r.raise_for_status()
    with open(destino, "wb") as f:
        f.write(r.content)
    print(f"[nyctus] video descargado: {destino}")

    # Avisar a Render que ya lo tomamos, para que /video-pendiente deje de
    # ofrecerlo mientras lo procesamos (puede tardar varios minutos).
    try:
        requests.post(f"{API_URL}/video-pendiente/confirmar", timeout=10)
    except requests.exceptions.RequestException as e:
        print(f"[nyctus] aviso: no se pudo confirmar video-pendiente: {e}")

    return destino


def subir_resultado(resultado):
    datos = {
        "ganado": str(resultado["ganado"]),
        "personas": "0",
        "duracion": str(resultado["duracion"]),
        "fecha": datetime.now().isoformat(),
    }
    try:
        with open(resultado["video_path"], "rb") as f:
            r = requests.post(
                f"{API_URL}/subir-analisis",
                data=datos,
                files={"file": (os.path.basename(resultado["video_path"]), f, "video/mp4")},
                timeout=120,
            )
        print(f"[nyctus] /subir-analisis -> {r.status_code}: {r.text[:200]}")
    except requests.exceptions.RequestException as e:
        print(f"[nyctus] error subiendo resultado a Render: {e}")


# ============================================================
# LOOP PRINCIPAL
# ============================================================
def main():
    print(f"[nyctus] worker YOLO escuchando a {API_URL} cada {POLL_SECONDS}s")
    while True:
        if hay_video_pendiente():
            try:
                video_local = descargar_video()
                resultado = procesar_video(video_local)
                if resultado:
                    subir_resultado(resultado)
            except Exception as e:
                print(f"[nyctus] error procesando video: {e}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()