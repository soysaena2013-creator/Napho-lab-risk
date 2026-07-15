import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 1. ตั้งค่าหน้า Dashboard
st.set_page_config(layout="wide", page_title="Laboratory Risk Dashboard")

# 2. โหลดและจัดการข้อมูล
@st.cache_data
def load_data():
    # ใช้ URL ที่ Publish มาจาก Google Sheets
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS8i7qAIxzDWkWCEnZZEjn8xLY8PT7edgUuTtEsh6aMjBHbj2qo-By5X7LxB1VjMovP9U-FUOkupWUm/pub?output=csv" 
    df = pd.read_csv(url)
    # จัดการชื่อคอลัมน์และวันที่ตามโครงสร้างไฟล์ของคุณ
    df['1.วันที่เกิดความเสี่ยง'] = pd.to_datetime(df['1.วันที่เกิดความเสี่ยง'], dayfirst=True)
    df['Year'] = df['1.วันที่เกิดความเสี่ยง'].dt.year
    df['Month'] = df['1.วันที่เกิดความเสี่ยง'].dt.month
    df['Quarter'] = df['1.วันที่เกิดความเสี่ยง'].dt.quarter
    return df

df = load_data()

# ฟังก์ชันคำนวณคะแนน
def get_freq_score(count):
    if count < 1: return 1
    elif count <= 5: return 2
    elif count <= 10: return 3
    else: return 4

def get_severity_score(sev_str):
    if pd.isna(sev_str): return 0
    code = str(sev_str).split(':')[0].strip().upper()
    mapping = {'A':1, 'B':1, 'C':2, 'D':2, 'E':3, 'F':3, 'G':4, 'H':4, 'I':4}
    return mapping.get(code, 0)

# 3. ส่วนกรองข้อมูล (Sidebar)
st.sidebar.header("Filter")
year_list = df['Year'].unique()
selected_year = st.sidebar.selectbox("เลือกปี", year_list)
selected_quarter = st.sidebar.multiselect("เลือกไตรมาส", [1, 2, 3, 4], default=[1, 2, 3, 4])
selected_type = st.sidebar.multiselect("ประเภทความเสี่ยง", df['5.ประเภทความเสี่ยง'].unique())
selected_dept = st.sidebar.multiselect("หน่วยงาน", df['4.หน่วยงานที่ทำให้เกิดความเสี่ยง'].unique())

# กรองข้อมูล
df_filtered = df[(df['Year'] == selected_year) & 
                 (df['Quarter'].isin(selected_quarter))]
if selected_type: df_filtered = df_filtered[df_filtered['5.ประเภทความเสี่ยง'].isin(selected_type)]
if selected_dept: df_filtered = df_filtered[df_filtered['4.หน่วยงานที่ทำให้เกิดความเสี่ยง'].isin(selected_dept)]

# 4. คำนวณความเสี่ยงรายไตรมาส (ตามเงื่อนไขที่ 4 และ 5)
# --- เริ่มแก้ไขที่ตำแหน่งประมาณบรรทัด 52 ---

# --- แทนที่บล็อกการคำนวณ risk_summary ด้วยชุดนี้ ---

# 1. ค้นหาชื่อคอลัมน์และรวบรวมข้อมูลความเสี่ยงย่อย
sev_col_name = [c for c in df.columns if 'ระดับความรุนแรงทางคลินิก' in c][0] 
risk_cols = [c for c in df.columns if 'ระบุความเสี่ยงย่อย' in c]

# 2. ทำ Melt ข้อมูลเพื่อรวมความเสี่ยงย่อยทั้งหมดเข้าด้วยกัน
df_melted = df_filtered.melt(id_vars=[sev_col_name], 
                             value_vars=risk_cols, 
                             value_name='Risk_Detail')

# 3. กรองเอาเฉพาะข้อมูลที่มีการระบุความเสี่ยง
df_melted = df_melted[df_melted['Risk_Detail'].notna() & (df_melted['Risk_Detail'] != '')]

# 4. จัดกลุ่มตาม "ความเสี่ยงย่อย" เท่านั้น (ไม่แยกหน่วยงาน)
# --- ส่วนการแสดงผล (วางแทนที่ส่วนแสดงผลตารางเดิม) ---

st.markdown("---")
# 1. แสดง Risk Matrix Visualization (แผนภูมิ)
st.subheader("Risk Matrix Visualization")
fig_matrix = px.scatter(risk_summary, x="Freq_Score", y="Sev_Score", size="Frequency", 
                        color="Risk_Matrix", hover_name="Risk_Detail",
                        range_x=[0.5, 4.5], range_y=[0.5, 4.5])
st.plotly_chart(fig_matrix, use_container_width=True)

# 2. แสดงตารางสรุปแบบไม่แยกหน่วยงานและไม่ต้องเลื่อน (ปรับ height)
st.subheader("ตารางสรุป Risk Matrix (รวมทุกหน่วยงาน)")
# ปรับให้แสดงผลได้กระชับขึ้นด้วยการเลือกเฉพาะคอลัมน์สำคัญ
st.dataframe(risk_summary[['Risk_Detail', 'Frequency', 'Freq_Score', 'Sev_Score', 'Risk_Matrix']], 
             use_container_width=True, 
             hide_index=True, 
             height=200) # ปรับความสูงเหลือ 200 เพื่อไม่ให้ต้องเลื่อนเยอะ
# --- สิ้นสุดการแก้ไข ---
# 5. แสดงผล Dashboard
st.title("🏥 Dashboard ติดตามความเสี่ยงห้องปฏิบัติการ")

col1, col2 = st.columns(2)
with col1:
    st.subheader("จำนวนความเสี่ยงแยกตามหน่วยงาน")
    fig1 = px.bar(df_filtered, x='4.หน่วยงานที่ทำให้เกิดความเสี่ยง', color='5.ประเภทความเสี่ยง')
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    st.subheader("ตารางสรุป Risk Matrix (เรียงลำดับความสำคัญ)")
    st.dataframe(risk_summary, use_container_width=True)

# 6. Risk Matrix Heatmap
st.subheader("Risk Matrix Visualization")
fig_matrix = px.density_heatmap(risk_summary, x="Freq_Score", y="Sev_Score", z="Risk_Matrix", 
                                color_continuous_scale="RdYlGn_r", 
                                labels={'Freq_Score': 'Frequency Score', 'Sev_Score': 'Severity Score'})
st.plotly_chart(fig_matrix, use_container_width=True)