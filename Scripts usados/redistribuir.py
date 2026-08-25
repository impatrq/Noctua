import os
import shutil
import random

# ─── CONFIGURACIÓN ────────────────────────────────────────────
DATASET_ENTRADA = r"C:\Users\juanc\Desktop\DATASET_FUSIONADO_V2"
DATASET_SALIDA  = r"C:\Users\juanc\Desktop\DATASET_FUSIONADO_FINAL"

PORC_TRAIN = 0.80
PORC_VALID = 0.10
PORC_TEST  = 0.10

SEED = 42  # Para que la división sea reproducible
# ──────────────────────────────────────────────────────────────

random.seed(SEED)

# Juntar todas las imágenes de todos los splits en una lista
todas_imagenes = []
for split in ["train", "valid", "test"]:
    carpeta = os.path.join(DATASET_ENTRADA, split, "images")
    if not os.path.exists(carpeta):
        continue
    for archivo in os.listdir(carpeta):
        if archivo.lower().endswith((".jpg", ".jpeg", ".png")):
            todas_imagenes.append((split, archivo))

print(f"Total imágenes encontradas: {len(todas_imagenes)}")

# Mezclar aleatoriamente
random.shuffle(todas_imagenes)

# Calcular cortes
total     = len(todas_imagenes)
n_train   = int(total * PORC_TRAIN)
n_valid   = int(total * PORC_VALID)

asignacion = (
    [("train", img) for _, img in todas_imagenes[:n_train]] +
    [("valid", img) for _, img in todas_imagenes[n_train:n_train + n_valid]] +
    [("test",  img) for _, img in todas_imagenes[n_train + n_valid:]]
)

# Crear carpetas de salida
for split in ["train", "valid", "test"]:
    for sub in ["images", "labels"]:
        os.makedirs(os.path.join(DATASET_SALIDA, split, sub), exist_ok=True)

# Copiar archivos
copiadas = 0
sin_label = 0

for nuevo_split, (split_original, archivo) in zip(
    [a[0] for a in asignacion], todas_imagenes
):
    nombre_base = os.path.splitext(archivo)[0]
    ext         = os.path.splitext(archivo)[1]

    # Imagen
    src_img = os.path.join(DATASET_ENTRADA, split_original, "images", archivo)
    dst_img = os.path.join(DATASET_SALIDA, nuevo_split, "images", archivo)
    shutil.copy2(src_img, dst_img)

    # Label
    src_lbl = os.path.join(DATASET_ENTRADA, split_original, "labels", nombre_base + ".txt")
    dst_lbl = os.path.join(DATASET_SALIDA, nuevo_split, "labels", nombre_base + ".txt")

    if os.path.exists(src_lbl):
        shutil.copy2(src_lbl, dst_lbl)
    else:
        open(dst_lbl, "w").close()
        sin_label += 1

    copiadas += 1

# Copiar data.yaml
shutil.copy2(
    os.path.join(DATASET_ENTRADA, "data.yaml"),
    os.path.join(DATASET_SALIDA, "data.yaml")
)

# Resumen
print("\n" + "="*50)
print(f"✓ Total procesadas: {copiadas}")
print(f"✓ Sin label (imágenes negativas): {sin_label}")
print(f"\nDistribución final:")
for split in ["train", "valid", "test"]:
    ruta = os.path.join(DATASET_SALIDA, split, "images")
    print(f"  {split}: {len(os.listdir(ruta))} imágenes")
print(f"\n✓ Dataset listo en: {DATASET_SALIDA}")