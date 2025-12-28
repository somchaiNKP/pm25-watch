import streamlit as st
import pandas as pd
import requests
import joblib
from datetime import datetime
import pytz # ไลบรารีสำหรับจัดการ Timezone

# ==========================================
# 1. โหลดโมเดล
# ==========================================
@st.cache_resource
def load_model():
    try:
        return joblib.load('pm25_klong1_model.pkl')
    except:
        return None

model = load_model()

# ==========================================
# 2. ฟังก์ชันดึงข้อมูล (เพิ่มการดึง PM 2.5 จริง)
# ==========================================
def get_realtime_data_full(owm_key, tomtom_key):
    wind, traffic, actual_pm25 = 0.0, 0.0, None
    lat, lon = 14.0742, 100.6152 # พิกัดคลองหนึ่ง
    
    # 2.1 ดึงลม (Weather API)
    try:
        url_weather = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={owm_key}&units=metric"
        resp = requests.get(url_weather)
        wind = resp.json()['wind']['speed']
    except:
        pass # ถ้า Error ให้ใช้ค่า 0 ไปก่อน

    # 2.2 ดึงค่าฝุ่นจริง (Air Pollution API) - *ของใหม่*
    try:
        url_air = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={owm_key}"
        resp = requests.get(url_air)
        # OWM ส่งค่ามาเป็น List เอาตัวแรกสุด
        actual_pm25 = resp.json()['list'][0]['components']['pm2_5']
    except:
        actual_pm25 = None # ดึงไม่ได้ไม่เป็นไร

    # 2.3 ดึงรถติด (TomTom API)
    try:
        url_traffic = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?point={lat},{lon}&key={tomtom_key}"
        resp = requests.get(url_traffic)
        data = resp.json()['flowSegmentData']
        traffic_score = (1 - (data['currentSpeed'] / data['freeFlowSpeed'])) * 10
        traffic = round(max(0, min(10, traffic_score)), 2)
    except:
        pass

    return wind, traffic, actual_pm25

# ==========================================
# 3. UI ส่วนแสดงผล
# ==========================================
st.set_page_config(page_title="PM 2.5 Live Monitor", page_icon="📡", layout="wide")

st.title("📡 PM 2.5 Watch @คลองหนึ่ง (Live Compare)")
st.markdown("ระบบพยากรณ์และเปรียบเทียบค่าฝุ่นแบบ Real-time")

# --- เวลาปัจจุบัน ---
tz = pytz.timezone('Asia/Bangkok')
current_time = datetime.now(tz).strftime("%d/%m/%Y %H:%M:%S")
st.info(f"🕒 เวลาตรวจสอบล่าสุด: **{current_time}**")

# --- Sidebar ---
st.sidebar.header("⚙️ Control Panel")
mode = st.sidebar.radio("Mode:", ["🌐 Real-time Monitor", "🎮 Simulation"])

# ตัวแปรสำหรับเก็บค่า
wind = 0.0
traffic = 0.0
actual_pm25 = None
predicted_pm25 = 0.0

if mode == "🌐 Real-time Monitor":
    st.sidebar.subheader("API Configuration")
    
    # ⚠️ ใส่ KEY ของคุณตรง value="..." เหมือนเดิมนะครับ
    owm_key = st.sidebar.text_input("OpenWeatherMap Key", value="a013dafdc6052c44dbcc4a1526beb43a", type="password")
    tomtom_key = st.sidebar.text_input("TomTom Key", value="3jXFI0SBVjEHLS2d3k4A5XcFgQwN3fzE", type="password")
    
    if st.sidebar.button("🚀 อัปเดตข้อมูลเดี๋ยวนี้"):
        with st.spinner('กำลังเชื่อมต่อดาวเทียมและเซนเซอร์...'):
            wind, traffic, actual_pm25 = get_realtime_data_full(owm_key, tomtom_key)
            st.session_state['wind'] = wind
            st.session_state['traffic'] = traffic
            st.session_state['actual_pm25'] = actual_pm25
            st.success("อัปเดตเสร็จสิ้น!")

    # ดึงค่าจาก Session ถ้ามี
    if 'wind' in st.session_state:
        wind = st.session_state['wind']
        traffic = st.session_state['traffic']
        actual_pm25 = st.session_state.get('actual_pm25', None)

elif mode == "🎮 Simulation":
    wind = st.sidebar.slider("ลม (m/s)", 0.0, 20.0, 5.0)
    traffic = st.sidebar.slider("รถติด (0-10)", 0.0, 10.0, 5.0)
    actual_pm25 = st.sidebar.number_input("สมมติค่าฝุ่นจริง (เพื่อเทียบ)", value=0.0)

# ==========================================
# 4. คำนวณและแสดงผล (Dashboard)
# ==========================================
if model:
    # คำนวณ AI (สูตรเดิม)
    input_df = pd.DataFrame([[traffic, wind]], columns=['Traffic_Score', 'Wind_Speed'])
    base_prediction = model.predict(input_df)[0]
    
    # 🔧 จูนค่าพิเศษ (Seasonal Adjustment)
    # สมมติว่าช่วงนี้มีการเผา หรือความกดอากาศต่ำ ทำให้ฝุ่นสะสมง่ายกว่าปกติ 5-8 เท่า
    # เราจะลองบวกค่าชดเชยเข้าไป (Bias)
    seasonal_offset = 80.0  # สมมติว่าฐานฝุ่นช่วงนี้สูงกว่าปกติ 80 หน่วย
    
    predicted_pm25 = base_prediction + seasonal_offset
    
    st.divider()

    # Layout: แบ่งเป็น 2 ส่วนหลัก
    # ส่วนบน: ปัจจัยนำเข้า (Inputs)
    col1, col2 = st.columns(2)
    col1.metric("🌬️ ความเร็วลม (Wind)", f"{wind} m/s")
    col2.metric("🚗 สภาพจราจร (Traffic)", f"{traffic}/10")
    
    st.divider()
    
    # ส่วนล่าง: ไฮไลท์สำคัญ (Comparison)
    st.subheader("🆚 ผลการวัด vs การพยากรณ์")
    
    m1, m2, m3 = st.columns(3)
    
    # 1. AI พยากรณ์
    with m1:
        st.metric(
            label="🤖 AI พยากรณ์ (Predicted)",
            value=f"{predicted_pm25:.2f}",
            delta="จากโมเดลของคุณ",
            delta_color="off"
        )
        
    # 2. ค่าจริง (Actual)
    with m2:
        if actual_pm25 is not None:
            st.metric(
                label="vivitar เซนเซอร์วัดจริง (Actual)",
                value=f"{actual_pm25:.2f}",
                delta="จาก OpenWeatherMap"
            )
        else:
            st.warning("ไม่มีข้อมูลจริง (Simulation หรือดึง API ไม่ผ่าน)")

    # 3. ความแม่นยำ (Error Difference)
    with m3:
        if actual_pm25 is not None and actual_pm25 > 0:
            diff = predicted_pm25 - actual_pm25
            error_percent = abs(diff / actual_pm25) * 100
            
            # ตกแต่งการแสดงผล
            if abs(diff) < 5: 
                status = "แม่นยำมาก! ✅"
                color = "normal"
            else: 
                status = "คลาดเคลื่อน ⚠️"
                color = "inverse"
                
            st.metric(
                label="📉 ความต่าง (Diff)",
                value=f"{diff:+.2f}", # แสดงเครื่องหมาย + หรือ -
                delta=status,
                delta_color=color
            )
            st.caption(f"Error: {error_percent:.1f}%")
        else:
            st.info("รอข้อมูลจริงเพื่อเปรียบเทียบ")

else:
    st.error("ไม่พบไฟล์โมเดล .pkl")