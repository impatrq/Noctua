import cv2
import tkinter as tk
from tkinter import filedialog, ttk
from ultralytics import YOLO
import threading
import os

# ─── CONFIGURACIÓN ────────────────────────────────────────────
MODELO_PATH = r"C:\Users\juanc\OneDrive\Desktop\NYCTUS\models\best.pt"
CONFIANZA   = 0.5
# ──────────────────────────────────────────────────────────────

modelo = YOLO(MODELO_PATH)

class InterfazNYCTUS:
    def __init__(self, root):
        self.root = root
        self.root.title("NYCTUS - Detección de Ganado")
        self.root.geometry("500x350")
        self.root.configure(bg="#1e1e1e")

        tk.Label(root, text="NYCTUS", font=("Arial", 28, "bold"),
                 bg="#1e1e1e", fg="white").pack(pady=20)
        tk.Label(root, text="Sistema de Detección de Ganado Bovino",
                 font=("Arial", 11), bg="#1e1e1e", fg="#aaaaaa").pack()

        tk.Button(root, text="  Subir video y procesar",
                  font=("Arial", 13), bg="#2d8c4e", fg="white",
                  padx=20, pady=10, bd=0, cursor="hand2",
                  command=self.seleccionar_video).pack(pady=30)

        self.progreso_var = tk.DoubleVar()
        self.barra = ttk.Progressbar(root, variable=self.progreso_var,
                                     maximum=100, length=400)
        self.barra.pack()

        self.estado = tk.Label(root, text="Esperando video...",
                               font=("Arial", 10), bg="#1e1e1e", fg="#aaaaaa")
        self.estado.pack(pady=8)

        # Label extra para mostrar el conteo final
        self.conteo_label = tk.Label(root, text="",
                                     font=("Arial", 13, "bold"),
                                     bg="#1e1e1e", fg="#2d8c4e")
        self.conteo_label.pack(pady=5)

    def seleccionar_video(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar video",
            filetypes=[("Videos", "*.mp4 *.avi *.mov *.mkv")]
        )
        if ruta:
            self.conteo_label.config(text="")
            hilo = threading.Thread(target=self.procesar_video, args=(ruta,))
            hilo.daemon = True
            hilo.start()

    def procesar_video(self, ruta_entrada):
        self.estado.config(text="Procesando...")
        self.progreso_var.set(0)

        cap = cv2.VideoCapture(ruta_entrada)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps    = cap.get(cv2.CAP_PROP_FPS)
        ancho  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        alto   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        nombre      = os.path.splitext(os.path.basename(ruta_entrada))[0]
        carpeta     = os.path.dirname(ruta_entrada)
        ruta_salida = os.path.join(carpeta, f"{nombre}_procesado.mp4")

        writer = cv2.VideoWriter(ruta_salida,
                                 cv2.VideoWriter_fourcc(*"mp4v"),
                                 fps, (ancho, alto))

        # Set que acumula todos los IDs únicos vistos en el video
        ids_unicos = set()
        frame_actual = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # Tracking en lugar de detección simple
            resultados = modelo.track(frame, conf=CONFIANZA,
                                      persist=True, verbose=False)[0]

            # Acumular IDs únicos
            if resultados.boxes.id is not None:
                ids_frame = resultados.boxes.id.int().tolist()
                ids_unicos.update(ids_frame)

            total_unico = len(ids_unicos)
            en_frame    = len(resultados.boxes)

            # Dibujar bounding boxes con IDs
            frame_anotado = resultados.plot()

            # Panel de información
            cv2.rectangle(frame_anotado, (10, 10), (380, 80), (0, 0, 0), -1)
            cv2.putText(frame_anotado,
                        f"En escena: {en_frame}",
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX,
                        1.0, (0, 255, 80), 2)
            cv2.putText(frame_anotado,
                        f"Total unicas: {total_unico}",
                        (20, 72), cv2.FONT_HERSHEY_SIMPLEX,
                        1.0, (0, 200, 255), 2)

            writer.write(frame_anotado)

            frame_actual += 1
            progreso = (frame_actual / total_frames) * 100
            self.progreso_var.set(progreso)
            self.root.update_idletasks()

        cap.release()
        writer.release()

        # Mostrar resultado final en la interfaz
        self.estado.config(text=f"✓ Guardado en: {ruta_salida}")
        self.conteo_label.config(text=f" Total vacas únicas detectadas: {len(ids_unicos)}")
        self.progreso_var.set(100)

# ─── MAIN ─────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app = InterfazNYCTUS(root)
    root.mainloop()