import os
import shutil
import hashlib
import yaml

# ─── CONFIGURACIÓN ────────────────────────────────────────────
DESKTOP = r"C:\Users\juanc\Desktop"

DATASETS = [
    os.path.join(DESKTOP, f"DATASETDEGOOGLE{i}")
    for i in [1, 2, 4, 6, 7, 8, 9, 10]
]

DATASET_FINAL = os.path.join(DESKTOP, "DATASET_FUSIONADO_V2")
SPLITS        = ["train", "valid", "test"]
# ──────────────────────────────────────────────────────────────

def hash_archivo(ruta):
    """Devuelve el hash MD5 del contenido de un archivo."""
    h = hashlib.md5()
    with open(ruta, "rb") as f:
        h.update(f.read())
    return h.hexdigest()

def obtener_clase_0(data_yaml):
    """Lee el data.yaml y devuelve el nombre de la clase 0."""
    try:
        with open(data_yaml, "r") as f:
            data = yaml.safe_load(f)
        nombres = data.get("names", [])
        if isinstance(nombres, list):
            return nombres[0].lower() if nombres else None
        elif isinstance(nombres, dict):
            return nombres.get(0, "").lower()
    except:
        return None

def remap_labels(txt_path, clase_original):
    """
    Si el dataset usa un nombre distinto a 'cow' como clase 0,
    igual lo acepta porque ya normalizamos todo a índice 0 = cow.
    Solo filtra líneas que no sean clase 0.
    """
    lineas_validas = []
    try:
        with open(txt_path, "r") as f:
            for linea in f:
                linea = linea.strip()
                if linea:
                    clase_idx = int(linea.split()[0])
                    if clase_idx == 0:
                        lineas_validas.append(linea)
    except:
        pass
    return lineas_validas

# Crear carpetas de salida
for split in SPLITS:
    for sub in ["images", "labels"]:
        os.makedirs(os.path.join(DATASET_FINAL, split, sub), exist_ok=True)

hashes_vistos = set()
contador      = {"copiadas": 0, "duplicadas": 0, "sin_split": 0}

for dataset_path in DATASETS:
    nombre_dataset = os.path.basename(dataset_path)
    yaml_path      = os.path.join(dataset_path, "data.yaml")
    clase_0        = obtener_clase_0(yaml_path)

    print(f"\n📂 Procesando: {nombre_dataset} (clase 0: '{clase_0}')")

    for split in SPLITS:
        carpeta_img = os.path.join(dataset_path, split, "images")
        carpeta_lbl = os.path.join(dataset_path, split, "labels")

        # Algunos datasets solo tienen train
        if not os.path.exists(carpeta_img):
            contador["sin_split"] += 1
            continue

        for archivo in os.listdir(carpeta_img):
            if not archivo.lower().endswith((".jpg", ".jpeg", ".png")):
                continue

            ruta_img = os.path.join(carpeta_img, archivo)
            hash_img = hash_archivo(ruta_img)

            # Saltar duplicados
            if hash_img in hashes_vistos:
                contador["duplicadas"] += 1
                continue
            hashes_vistos.add(hash_img)

            # Nombre único de salida
            nombre_base = os.path.splitext(archivo)[0]
            ext_img     = os.path.splitext(archivo)[1]
            nuevo_nombre = f"{nombre_dataset}_{split}_{nombre_base}"

            # Copiar imagen
            dst_img = os.path.join(DATASET_FINAL, split, "images",
                                   nuevo_nombre + ext_img)
            shutil.copy2(ruta_img, dst_img)

            # Copiar y limpiar label
            ruta_txt = os.path.join(carpeta_lbl, nombre_base + ".txt")
            dst_txt  = os.path.join(DATASET_FINAL, split, "labels",
                                    nuevo_nombre + ".txt")

            if os.path.exists(ruta_txt):
                lineas = remap_labels(ruta_txt, clase_0)
                with open(dst_txt, "w") as f:
                    f.write("\n".join(lineas))
            else:
                # Imagen sin label = imagen negativa, crear txt vacío
                open(dst_txt, "w").close()

            contador["copiadas"] += 1

# Generar data.yaml final
yaml_final = {
    "train": "../train/images",
    "val":   "../valid/images",
    "test":  "../test/images",
    "nc":    1,
    "names": ["cow"]
}
with open(os.path.join(DATASET_FINAL, "data.yaml"), "w") as f:
    yaml.dump(yaml_final, f, default_flow_style=False, allow_unicode=True)

# Resumen
print("\n" + "="*50)
print(f"✓ Imágenes copiadas:   {contador['copiadas']}")
print(f"✓ Duplicadas saltadas: {contador['duplicadas']}")
print(f"✓ Splits no encontrados (normal): {contador['sin_split']}")
print(f"✓ data.yaml generado")
print(f"✓ Dataset final en: {DATASET_FINAL}")

# Conteo por split
print("\nDistribución final:")
for split in SPLITS:
    ruta = os.path.join(DATASET_FINAL, split, "images")
    if os.path.exists(ruta):
        print(f"  {split}: {len(os.listdir(ruta))} imágenes")