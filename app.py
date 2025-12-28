import streamlit as st
import pandas as pd
import requests
import joblib
from datetime import datetime
import pytz

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
# 2. ฟังก์ชันดึงข้อมูล (เหมือนเดิม)
# ==========================================
def get_realtime_data_full(owm_key, tomtom_key):
    wind, traffic, actual_pm25 = 0.0, 0.0, None
    lat, lon = 14.0742, 100.6152
    
    try:
        url_weather = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={owm_key}&units=metric"
        resp = requests.get(url_weather)
        wind = resp.json()['wind']['speed']
    except: pass

    try:
        url_air = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={owm_key}"
        resp = requests.get(url_air)
        actual_pm25 = resp.json()['list'][0]['components']['pm2_5']
    except: actual_pm25 = None

    try:
        url_traffic = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?point={lat},{lon}&key={tomtom_key}"
        resp = requests.get(url_traffic)
        data = resp.json()['flowSegmentData']
        traffic_score = (1 - (data['currentSpeed'] / data['freeFlowSpeed'])) * 10
        traffic = round(max(0, min(10, traffic_score)), 2)
    except: pass

    return wind, traffic, actual_pm25

# ==========================================
# 3. UI ส่วนแสดงผล (ปรับแก้เพื่อมือถือ)
# ==========================================
# ❌ ลบ layout="wide" ออก เพื่อให้พอดีจอมือถือ
st.set_page_config(page_title="PM 2.5 Mobile", page_icon="📱")

st.title("📱 PM 2.5 Watch")
st.caption("📍 พิกัด: คลองหนึ่ง (Mobile Version)")

# แสดงเวลา
tz = pytz.timezone('Asia/Bangkok')
current_time = datetime.now(tz).strftime("%H:%M น. (%d/%m)")
st.info(f"🕒 อัปเดตล่าสุด: {current_time}")

# --- Sidebar ---
st.sidebar.header("⚙️ ตั้งค่า")
mode = st.sidebar.radio("โหมด:", ["🌐 Real-time", "🎮 จำลองค่า"])

wind, traffic, actual_pm25, predicted_pm25 = 0.0, 0.0, None, 0.0

if mode == "🌐 Real-time":
    # ใส่ API Key ตรง value เหมือนเดิม
    owm_key = st.sidebar.text_input("OWM Key", value="a013dafdc6052c44dbcc4a1526beb43a", type="password")
    tomtom_key = st.sidebar.text_input("TomTom Key", value="3jXFI0SBVjEHLS2d3k4A5XcFgQwN3fzE", type="password")
    
    if st.button("🔄 กดเพื่อดึงข้อมูลล่าสุด", use_container_width=True): # ปุ่มกว้างเต็มจอ กดง่าย
        with st.spinner('กำลังโหลด...'):
            wind, traffic, actual_pm25 = get_realtime_data_full(owm_key, tomtom_key)
            st.session_state['wind'] = wind
            st.session_state['traffic'] = traffic
            st.session_state['actual_pm25'] = actual_pm25
    
    if 'wind' in st.session_state:
        wind = st.session_state['wind']
        traffic = st.session_state['traffic']
        actual_pm25 = st.session_state.get('actual_pm25', None)

elif mode == "🎮 จำลองค่า":
    wind = st.slider("ลม (m/s)", 0.0, 20.0, 5.0)
    traffic = st.slider("รถติด (0-10)", 0.0, 10.0, 5.0)
    actual_pm25 = st.number_input("ค่าจริง (เทียบ)", value=0.0)

# ==========================================
# 4. Dashboard (จัดเรียงแนวตั้ง)
# ==========================================
if model:
    # คำนวณ + จูนค่า
    input_df = pd.DataFrame([[traffic, wind]], columns=['Traffic_Score', 'Wind_Speed'])
    base_pred = model.predict(input_df)[0]
    seasonal_offset = 80.0 # ค่าจูน (Calibration)
    predicted_pm25 = base_pred + seasonal_offset

    st.markdown("---")

    # ส่วนที่ 1: ปัจจัย (Input) - ใช้ 2 คอลัมน์พอกล้อมแกล้ม
    c1, c2 = st.columns(2)
    c1.metric("🌬️ ลม", f"{wind} m/s")
    c2.metric("🚗 รถ", f"{traffic}/10")

    st.markdown("---")
    
    # ส่วนที่ 2: ผลลัพธ์ (Result) - เรียงแนวตั้งให้ชัดๆ
    st.subheader("📊 ผลวิเคราะห์")

    # กล่องที่ 1: AI (พระเอกของเรา)
    with st.container():
        st.markdown("#### 🤖 AI พยากรณ์")
        if predicted_pm25 > 50:
            st.error(f"⚠️ {predicted_pm25:.2f} (อันตราย)")
        elif predicted_pm25 > 37.5:
            st.warning(f"🟠 {predicted_pm25:.2f} (เริ่มแย่)")
        else:
            st.success(f"🟢 {predicted_pm25:.2f} (อากาศดี)")

    # กล่องที่ 2: ค่าจริง (ถ้ามี)
    if actual_pm25 is not None:
        with st.container():
            st.markdown("#### 📡 ค่าจริงจากเซนเซอร์")
            st.info(f"{actual_pm25:.2f} µg/m³")
            
            # คำนวณ Diff
            diff = predicted_pm25 - actual_pm25
            msg = f"แม่นยำ (ต่างกัน {diff:.1f})" if abs(diff) < 20 else f"คลาดเคลื่อน ({diff:+.1f})"
            st.caption(f"ผลประเมิน: {msg}")

else:
    st.error("ไม่พบไฟล์โมเดล")