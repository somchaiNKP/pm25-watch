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
# 2. ฟังก์ชันหาพิกัดจากชื่อเมือง (Geocoding) - **ของใหม่**
# ==========================================
def get_coordinates(city_name, api_key):
    # ค้นหาพิกัดจากชื่อเมือง (เติม ,TH ต่อท้ายเพื่อให้รู้ว่าเป็นไทย)
    try:
        url = f"http://api.openweathermap.org/geo/1.0/direct?q={city_name},TH&limit=1&appid={api_key}"
        resp = requests.get(url, timeout=5)
        data = resp.json()
        
        if data:
            lat = data[0]['lat']
            lon = data[0]['lon']
            found_name = data[0]['name']
            return lat, lon, found_name
        else:
            return None, None, None
    except:
        return None, None, None

# ==========================================
# 3. ฟังก์ชันดึงข้อมูล (รับ Lat/Lon แบบ Dynamic)
# ==========================================
def get_realtime_data_dynamic(lat, lon, owm_key, tomtom_key):
    wind, traffic, actual_pm25 = 0.0, 0.0, None
    
    # 3.1 ดึงลม
    try:
        url_weather = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={owm_key}&units=metric"
        resp = requests.get(url_weather, timeout=5)
        wind = resp.json()['wind']['speed']
    except: pass

    # 3.2 ดึงฝุ่นจริง
    try:
        url_air = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={owm_key}"
        resp = requests.get(url_air, timeout=5)
        actual_pm25 = resp.json()['list'][0]['components']['pm2_5']
    except: actual_pm25 = None

    # 3.3 ดึงรถติด
    try:
        url_traffic = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?point={lat},{lon}&key={tomtom_key}"
        resp = requests.get(url_traffic, timeout=5)
        data = resp.json()['flowSegmentData']
        # สูตร: ถ้าไม่มีข้อมูล FreeFlow ให้ใช้ค่า SpeedLimit แทน
        free_flow = data.get('freeFlowSpeed', data['currentSpeed']) 
        if free_flow > 0:
            traffic_score = (1 - (data['currentSpeed'] / free_flow)) * 10
        else:
            traffic_score = 0
        traffic = round(max(0, min(10, traffic_score)), 2)
    except: pass

    return wind, traffic, actual_pm25

# ==========================================
# 4. UI ส่วนแสดงผล (Thailand Edition)
# ==========================================
st.set_page_config(page_title="PM 2.5 TH", page_icon="🇹🇭")

st.title("🇹🇭 PM 2.5 Thailand")
st.caption("ระบบพยากรณ์ฝุ่นระดับอำเภอ")

tz = pytz.timezone('Asia/Bangkok')
current_time = datetime.now(tz).strftime("%H:%M น.")
st.info(f"🕒 เวลาตรวจสอบ: {current_time}")

# --- Sidebar ---
st.sidebar.header("⚙️ ตั้งค่า")
mode = st.sidebar.radio("โหมด:", ["🌐 Real-time", "🎮 Simulation"])

# ตัวแปรเริ่มต้น
wind, traffic, actual_pm25, predicted_pm25 = 0.0, 0.0, None, 0.0
location_name = "ยังไม่ระบุ"

if mode == "🌐 Real-time":
    # 1. รับ API Key
    owm_key = st.sidebar.text_input("OWM Key", value="a013dafdc6052c44dbcc4a1526beb43a", type="password")
    tomtom_key = st.sidebar.text_input("TomTom Key", value="3jXFI0SBVjEHLS2d3k4A5XcFgQwN3fzE", type="password")
    
    st.sidebar.markdown("---")
    
    # 2. รับชื่อเมือง (ภาษาอังกฤษจะแม่นยำกว่า)
    user_city = st.sidebar.text_input("🔍 ชื่ออำเภอ/เขต (ภาษาอังกฤษ)", value="Pathum Wan")
    st.sidebar.caption("ตัวอย่าง: Chatuchak, Mueang Chiang Mai, Hat Yai")

    # 3. ปุ่มค้นหา
    if st.button("📍 ค้นหาและพยากรณ์", use_container_width=True):
        if not owm_key or not tomtom_key:
            st.error("กรุณาใส่ API Key ก่อนครับ")
        else:
            with st.spinner(f"กำลังบินไปที่ {user_city}..."):
                # หาพิกัดก่อน
                lat, lon, found_name = get_coordinates(user_city, owm_key)
                
                if lat:
                    st.success(f"เจอพิกัด: {found_name} ({lat:.2f}, {lon:.2f})")
                    location_name = found_name
                    
                    # ดึงข้อมูลจากพิกัดนั้น
                    wind, traffic, actual_pm25 = get_realtime_data_dynamic(lat, lon, owm_key, tomtom_key)
                    
                    # บันทึกสถานะ
                    st.session_state['wind'] = wind
                    st.session_state['traffic'] = traffic
                    st.session_state['actual_pm25'] = actual_pm25
                    st.session_state['location'] = location_name
                else:
                    st.error("❌ หาชื่อเมืองไม่เจอ ลองพิมพ์เป็นภาษาอังกฤษดูครับ (เช่น 'Bang Rak')")

    # ดึงค่าเก่ามาแสดงถ้ามี
    if 'wind' in st.session_state:
        wind = st.session_state['wind']
        traffic = st.session_state['traffic']
        actual_pm25 = st.session_state.get('actual_pm25', None)
        location_name = st.session_state.get('location', user_city)

elif mode == "🎮 Simulation":
    location_name = "โหมดจำลอง"
    wind = st.slider("ลม (m/s)", 0.0, 20.0, 5.0)
    traffic = st.slider("รถติด (0-10)", 0.0, 10.0, 5.0)
    actual_pm25 = st.number_input("ค่าจริง (เทียบ)", value=0.0)

# ==========================================
# 5. Dashboard
# ==========================================
if model:
    # 📍 ส่วนหัวข้อ (แสดงชื่อเมือง)
    st.markdown(f"### 🚩 พื้นที่: {location_name}")

    # คำนวณ AI
    input_df = pd.DataFrame([[traffic, wind]], columns=['Traffic_Score', 'Wind_Speed'])
    base_pred = model.predict(input_df)[0]
    
    # 🔧 Calibration Slider (สำคัญมากสำหรับต่างจังหวัด)
    # เพราะเชียงใหม่กับกรุงเทพฯ มีค่าฝุ่นพื้นฐานไม่เท่ากัน
    with st.expander("🛠️ ปรับจูนค่าพื้นฐาน (Calibration)"):
        seasonal_offset = st.slider("ระดับฝุ่นพื้นฐานในพื้นที่ (Offset)", 0.0, 200.0, 80.0, help="ปรับเพิ่มลดตามฤดูกาลหรือพื้นที่")
    
    predicted_pm25 = base_pred + seasonal_offset

    st.markdown("---")
    
    # Grid Layout
    c1, c2 = st.columns(2)
    c1.metric("🌬️ ลม", f"{wind} m/s")
    c2.metric("🚗 รถ", f"{traffic}/10")

    st.markdown("---")
    st.subheader("📊 ผลวิเคราะห์")

    # AI Result
    with st.container():
        st.markdown("#### 🤖 AI พยากรณ์")
        if predicted_pm25 > 50:
            st.error(f"⚠️ {predicted_pm25:.2f} (อันตราย)")
        elif predicted_pm25 > 37.5:
            st.warning(f"🟠 {predicted_pm25:.2f} (เริ่มแย่)")
        else:
            st.success(f"🟢 {predicted_pm25:.2f} (อากาศดี)")

    # Actual Result
    if actual_pm25 is not None:
        with st.container():
            st.markdown("#### 📡 ค่าจริง (Sensor)")
            st.info(f"{actual_pm25:.2f} µg/m³")
            diff = predicted_pm25 - actual_pm25
            st.caption(f"Error: {diff:+.1f}")

else:
    st.error("ไม่พบไฟล์โมเดล")