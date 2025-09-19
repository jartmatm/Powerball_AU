import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.keras import layers, models
from url_years import urls
from bs4 import BeautifulSoup
import requests
# ======== 1) Scraping ========

all_data = []
for year, url in urls.items():
    print(f"Procesando sorteo {year}...")
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        ball = soup.find_all('li', class_='ball ball -b280')
        powerball = soup.find_all('li', class_='ball powerball -b280')

        for i in range(0, len(ball), 7):
            numeros = [int(q.text) for q in ball[i:i+7]]
            pb = int(powerball[i // 7].text) if (i // 7) < len(powerball) else 0
            all_data.append(numeros + [pb])

df = pd.DataFrame(all_data, columns=[f"Numero{i}" for i in range(1, 8)] + ["Powerball"])

# ======== 1) Preparar datos ========
num_cols = [f"Numero{i}" for i in range(1, 8)] + ["Powerball"]
df_nums = df[num_cols].copy().reset_index(drop=True)

# Convertir a enteros
for c in num_cols:
    df_nums[c] = pd.to_numeric(df_nums[c], errors="coerce")
df_nums = df_nums.dropna(subset=num_cols).astype(int).reset_index(drop=True)

# Pares alternos
X_rows = df_nums.iloc[::2].copy()
Y_rows = df_nums.iloc[1::2].copy()
m = min(len(X_rows), len(Y_rows))
X_rows, Y_rows = X_rows.iloc[:m].reset_index(drop=True), Y_rows.iloc[:m].reset_index(drop=True)

X_np, Y_np = X_rows.values.astype(np.float32), Y_rows.values.astype(np.float32)

# Escalado MinMax
both = np.vstack([X_np, Y_np])
col_max, col_min = both.max(axis=0).clip(min=1.0), both.min(axis=0)

def minmax_scale(a, cmin, cmax):
    return (a - cmin) / (cmax - cmin + 1e-8)

def minmax_inverse(a_scaled, cmin, cmax):
    return a_scaled * (cmax - cmin + 1e-8) + cmin

X_sc, Y_sc = minmax_scale(X_np, col_min, col_max), minmax_scale(Y_np, col_min, col_max)

# ======== 2) Definir modelo en TensorFlow ========
model = models.Sequential([
    layers.Input(shape=(8,)),
    layers.Dense(256, activation="relu"),
    layers.Dense(128, activation="relu"),
    layers.Dense(96, activation="relu"),
    layers.Dense(64, activation="relu"),
    layers.Dense(32, activation="relu"),
    layers.Dense(8, activation="sigmoid")  # salida 0-1
])

model.compile(optimizer=tf.keras.optimizers.Adam(1e-3),
              loss="mse")

# ======== 3) Entrenamiento ========
history = model.fit(X_sc, Y_sc, epochs=100, batch_size=32, shuffle=True, verbose=2)

# ======== 4) Helpers ========
def postprocess_prediction(vec_float):
    # Limitar los 7 números entre 1 y 35 y la powerball entre 1 y 20
    pred = np.rint(vec_float).astype(int)
    main = []
    used = set()
    for i in range(7):
        num = np.clip(pred[i], 1, 35)
        # Si el número ya fue usado, busca el siguiente disponible
        while num in used or num < 1 or num > 35:
            num += 1
            if num > 35:
                num = 1
        main.append(num)
        used.add(num)
    pb = np.clip(pred[7], 1, 20)
    return main, int(pb)


def predict_from_last_draw():
    last = df_nums.iloc[-1][num_cols].values.astype(np.float32).reshape(1, -1)
    last_sc = minmax_scale(last, col_min, col_max)
    out_sc = model.predict(last_sc, verbose=0)
    out_real = minmax_inverse(out_sc, col_min, col_max)[0]
    return postprocess_prediction(out_real)

# ======== 5) Ejemplo ========

nums_pred2, pb_pred2 = predict_from_last_draw()
print("Próximo sugerido desde el último sorteo:", nums_pred2, "| PB:", pb_pred2)

# ======== 6) Graficar curva de pérdida ========
""""atplotlib.pyplot as plt
plt.plot(history.history["loss"])
plt.xlabel("Epoch")
plt.ylabel("Loss")
plt.title("Learning Curve")
plt.show()
"""""