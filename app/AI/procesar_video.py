import cv2
import os
import json
import requests
from datetime import datetime
from ultralytics import YOLO

# ============================================================
# CONFIGURACIÓN
# ============================================================

MODELO_PATH = "best.pt"
VIDEO_ENTRADA = "videos/prueba.mp4"

CARPETA_PROCESADOS = "videos/procesados"
CARPETA_LABELS = "labels"

API_URL = "https://nyctus.onrender.com"

# ============================================================
# CREAR CARPETAS
# ============================================================

os.makedirs(CARPETA_PROCESADOS, exist_ok=True)
os.makedirs(CARPETA_LABELS, exist_ok=True)

# ============================================================
# CARGAR MODELO
# ============================================================

print("Cargando modelo YOLO...")
modelo = YOLO(MODELO_PATH)
print("Modelo cargado correctamente.")

# ============================================================
# ABRIR VIDEO
# ============================================================

cap = cv2.VideoCapture(VIDEO_ENTRADA)

if not cap.isOpened():
    print("ERROR: no se pudo abrir el video.")
    exit()

fps = cap.get(cv2.CAP_PROP_FPS)
ancho = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
alto = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
cantidad_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

if fps <= 0:
    fps = 30

duracion = cantidad_frames / fps

# ============================================================
# ARCHIVOS DE SALIDA
# ============================================================

nombre_video = os.path.splitext(
    os.path.basename(VIDEO_ENTRADA)
)[0]

VIDEO_SALIDA = os.path.join(
    CARPETA_PROCESADOS,
    f"{nombre_video}_procesado.mp4"
)

LABELS_SALIDA = os.path.join(
    CARPETA_LABELS,
    f"{nombre_video}_labels.json"
)

# ============================================================
# VIDEO WRITER
# ============================================================

writer = cv2.VideoWriter(
    VIDEO_SALIDA,
    cv2.VideoWriter_fourcc(*"mp4v"),
    fps,
    (ancho, alto)
)

# ============================================================
# VARIABLES
# ============================================================

ids_unicos = set()
detecciones = []
frame_numero = 0

print("\n========================================")
print("INICIANDO PROCESAMIENTO")
print("========================================")

# ============================================================
# PROCESAMIENTO (MISMO FLUJO QUE EL ORIGINAL)
# ============================================================

while cap.isOpened():

    ret, frame = cap.read()

    if not ret:
        break

    frame_numero += 1

    resultados = modelo.track(
        frame,
        conf=0.5,
        persist=True,
        verbose=False
    )[0]

    # --------------------------------------------------------
    # CONTAR IDS ÚNICOS
    # --------------------------------------------------------

    if resultados.boxes.id is not None:
        ids_frame = resultados.boxes.id.int().tolist()
        ids_unicos.update(ids_frame)

    en_frame = len(resultados.boxes)

    # --------------------------------------------------------
    # GUARDAR LABELS
    # --------------------------------------------------------

    if resultados.boxes is not None:

        cajas = resultados.boxes

        for i in range(len(cajas)):

            tracking_id = None

            if cajas.id is not None:
                tracking_id = int(cajas.id[i].item())

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
                "y2": float(y2)
            })

    # --------------------------------------------------------
    # FRAME ANOTADO ORIGINAL (SIN ZOOM)
    # --------------------------------------------------------

    frame_anotado = resultados.plot()
# Asegurar que el frame tenga exactamente el tamaño original
    if frame_anotado.shape[:2] != (alto, ancho):
        frame_anotado = cv2.resize(
            frame_anotado,
            (ancho, alto),
            interpolation=cv2.INTER_LINEAR
        )
    cv2.rectangle(
        frame_anotado,
        (10, 10),
        (380, 80),
        (0, 0, 0),
        -1
    )

    cv2.putText(
        frame_anotado,
        f"En escena: {en_frame}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 255, 80),
        2
    )

    cv2.putText(
        frame_anotado,
        f"Total unicas: {len(ids_unicos)}",
        (20, 72),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 200, 255),
        2
    )

    writer.write(frame_anotado)
    cv2.imshow("NYCTUS - IA", frame_anotado)

    if cv2.waitKey(1) & 0xFF == 27:
        break

# ============================================================
# FINALIZAR VIDEO
# ============================================================

cap.release()
writer.release()
cv2.destroyAllWindows()

# ============================================================
# RESULTADO FINAL
# ============================================================

total_ganado = len(ids_unicos)

print("\n========================================")
print("PROCESAMIENTO TERMINADO")
print("========================================")

print(f"Ganado detectado: {total_ganado}")
print(f"Duración: {duracion:.2f} segundos")
print(f"Video procesado: {VIDEO_SALIDA}")

# ============================================================
# GUARDAR LABELS.JSON
# ============================================================

datos_labels = {
    "video": os.path.basename(VIDEO_SALIDA),
    "fecha": datetime.now().isoformat(),
    "duracion_segundos": duracion,
    "total_ganado": total_ganado,
    "detecciones": detecciones
}

with open(
    LABELS_SALIDA,
    "w",
    encoding="utf-8"
) as archivo:

    json.dump(
        datos_labels,
        archivo,
        indent=4,
        ensure_ascii=False
    )

print(f"Labels guardados: {LABELS_SALIDA}")

# ============================================================
# ENVIAR RESULTADO A RENDER
# ============================================================

print("\nEnviando resultado a Render...")

datos = {
    "ganado": total_ganado,
    "personas": 0,
    "video": os.path.basename(VIDEO_SALIDA),
    "labels": os.path.basename(LABELS_SALIDA),
    "duracion": duracion,
    "fecha": datetime.now().isoformat()
}

try:

    respuesta = requests.post(
        f"{API_URL}/subir-analisis",
        json=datos,
        timeout=30
    )

    print("\n========================================")
    print("RESPUESTA DEL SERVIDOR")
    print("========================================")

    print(f"HTTP: {respuesta.status_code}")
    print(respuesta.text)

    if respuesta.status_code == 200:
        print("\n✓ Resultado enviado correctamente a Render.")
    else:
        print("\n✗ Render respondió con un código inesperado.")

except requests.exceptions.RequestException as error:

    print("\n========================================")
    print("ERROR AL CONECTAR CON RENDER")
    print("========================================")

    print(error)