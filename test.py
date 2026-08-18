import streamlit as st
import pandas as pd
import sqlite3
import serial
import time
import numpy as np
import threading
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score  # تم إضافة موديول حساب الدقة
from sklearn.model_selection import train_test_split # لتقسيم البيانات وحساب الدقة بشكل صحيح
import plotly.express as px
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

# ========= SETTINGS =========
ESP32_PORT = 'COM9'       # Change to your actual COM port
BAUD_RATE = 115200
DB_PATH = 'cargo_blackbox.db'
TRAINING_FILE = 'smart_cargo_training_data.csv'

# University of Jeddah - Al Faisaliyah Campus Coordinates
UJ_LAT = 21.5644
UJ_LNG = 39.1728

st.set_page_config(page_title="NeptuneX AI Dashboard", layout="wide")
st_autorefresh(interval=1000, key="refresh") # Refresh UI every 1 second

# --- Database & AI Functions ---
def create_database():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            temp REAL, hum REAL, gas REAL, water REAL, piezo REAL,
            risk REAL, status TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn

def train_ai_model():
    try:
        df = pd.read_csv(TRAINING_FILE)
        X = df[['temp', 'hum', 'gas', 'water', 'piezo']]
        y = df['risk_label']
        
        # تقسيم البيانات لاختبار دقة النموذج (80% تدريب، 20% اختبار)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X_train.values, y_train)
        
        # حساب الأكيورسي بناءً على بيانات الاختبار
        y_pred = model.predict(X_test.values)
        acc = accuracy_score(y_test, y_pred)
        
        # تخزين قيمة الأكيورسي في الـ Session State لعرضها بالداش بورد
        st.session_state['model_accuracy'] = acc
        
        return model
    except Exception as e:
        st.error(f"AI Model Training Error: {e}")
        return None

def get_status(risk):
    if risk < 40: return "SAFE"
    elif risk < 75: return "WARNING"
    return "CRITICAL"

# --- Background Serial Reader Thread ---
def serial_reader_thread(model):
    conn = create_database()
    c = conn.cursor()
    try:
        ser = serial.Serial(ESP32_PORT, BAUD_RATE, timeout=1)
        while True:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line.startswith("DATA"):
                    parts = line.split(",")
                    if len(parts) >= 6:
                        # Sensor Data
                        temp, hum, gas, water, piezo = map(float, parts[1:6])
                        
                        # AI Risk Prediction
                        current = np.array([[temp, hum, gas, water, piezo]])
                        probs = model.predict_proba(current)[0]
                        risk = float(probs[1] * 100) if len(probs) > 1 else 0.0
                        status = get_status(risk)
                        
                        # Save to Database
                        c.execute("""
                            INSERT INTO logs (temp, hum, gas, water, piezo, risk, status) 
                            VALUES (?,?,?,?,?,?,?)
                        """, (temp, hum, gas, water, piezo, round(risk, 2), status))
                        conn.commit()
            time.sleep(0.1)
    except Exception as e:
        print(f"Serial Error: {e}")

# --- Streamlit UI Layout ---
st.title("🚢 NeptuneX AI Dashboard")
st.markdown("### Location: University of Jeddah (Al Faisaliyah)")

# Start Serial Thread
if 'reader_started' not in st.session_state:
    ai_model = train_ai_model()
    if ai_model:
        thread = threading.Thread(target=serial_reader_thread, args=(ai_model,), daemon=True)
        thread.start()
        st.session_state['reader_started'] = True

# Data Fetching
def get_display_data():
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM logs ORDER BY timestamp DESC LIMIT 100", conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

df_logs = get_display_data()

if not df_logs.empty:
    last = df_logs.iloc[0]
    
    # 1. Sensors Grid
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("🌡️ Temp", f"{last['temp']} °C")
    m2.metric("💧 Humidity", f"{last['hum']} %")
    m3.metric("💨 Gas", f"{last['gas']}")
    m4.metric("🌊 Water", f"{last['water']}")
    m5.metric("🫨 Piezo", f"{last['piezo']}")

    # 2. AI Risk Level & Status & Model Accuracy
    st.divider()
    s1, s2, s3 = st.columns([1, 1, 2]) # تم زيادة الأعمدة إلى 3 لعرض الأكيورسي
    with s1:
        st.metric("⚠️ AI Risk", f"{last['risk']}%")
    with s2:
        # عرض دقة خوارزمية الـ Random Forest في كرت منفصل
        if 'model_accuracy' in st.session_state:
            accuracy_val = st.session_state['model_accuracy'] * 100
            st.metric("🎯 Model Accuracy", f"{accuracy_val:.2f}%")
    with s3:
        if last['status'] == "SAFE": st.success("STATUS: SAFE")
        elif last['status'] == "WARNING": st.warning("STATUS: WARNING")
        else: st.error("STATUS: CRITICAL")

    # 3. Destination Map (University of Jeddah)
    st.subheader("📍 Cargo Destination")
    map_df = pd.DataFrame({'lat': [UJ_LAT], 'lon': [UJ_LNG]})
    st.map(map_df)
    st.caption(f"University of Jeddah - Al Faisaliyah Campus ({UJ_LAT}, {UJ_LNG})")

    # 4. Analytics Charts
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(px.line(df_logs.iloc[::-1], x='timestamp', y='risk', title="AI Risk Trend"), use_container_width=True)
    with c2:
        st.plotly_chart(px.line(df_logs.iloc[::-1], x='timestamp', y=['temp', 'hum'], title="Environment Factors"), use_container_width=True)

    # 5. History Table
    st.subheader("📋 Recent Logs")
    st.dataframe(df_logs, use_container_width=True)
else:
    st.info("Waiting for data stream from ESP32...")