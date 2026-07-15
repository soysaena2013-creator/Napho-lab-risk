import streamlit as st
import pandas as pd
import plotly.express as px
# --- วางฟังก์ชันเหล่านี้ไว้ที่ส่วนบนของไฟล์ ต่อจาก import ---
def get_freq_score(count):
    if count > 10: return 4
    elif count >= 5: return 3
    elif count >= 1: return 2
    else: return 1

def get_sev_score(text):
    text = str(text).upper()
    if any(x in text for x in ['G', 'H', 'I']): return 4
    elif any(x in text for x in ['E', 'F']): return 3
    elif any(x in text for x in ['C', 'D']): return 2
    return 1
# ----------------------------------------------------
st.set_page_config(layout="wide")

# 1. โหลดข้อมูล
@st.cache_data
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS8i7qAIxzDWkWCEnZZEjn8xLY8PT7edgUuTtEsh6aMjBHbj2qo-By5X7LxB1VjMovP9U-FUOkupWUm/pub?output=csv" 
    df = pd.read_csv(url)
    df['Date'] = pd.to_datetime(df['1.วันที่เกิดความเสี่ยง'], dayfirst=True)
    return df

df = load_data()

# 2. Sidebar Filters (ข้อ 1, 2, 3)
st.sidebar.header("เครื่องมือสืบค้น")
year = st.sidebar.multiselect("เลือกปี", df['Date'].dt.year.unique())
quarter = st.sidebar.multiselect("เลือกไตรมาส", [1, 2, 3, 4])
risk_type = st.sidebar.multiselect("ประเภทความเสี่ยง", df['5.ประเภทความเสี่ยง'].unique())
unit = st.sidebar.multiselect("หน่วยงาน", df['4.หน่วยงานที่ทำให้เกิดความเสี่ยง'].unique())

df_f = df.copy()
if year: df_f = df_f[df_f['Date'].dt.year.isin(year)]
if quarter: df_f = df_f[df_f['Date'].dt.quarter.isin(quarter)]
if risk_type: df_f = df_f[df_f['5.ประเภทความเสี่ยง'].isin(risk_type)]
if unit: df_f = df_f[df_f['4.หน่วยงานที่ทำให้เกิดความเสี่ยง'].isin(unit)]

st.title("🏥 Dashboard ติดตามความเสี่ยงทางห้องปฏิบัติการ")

# แผนภูมิแท่งสรุปรายหน่วยงาน
st.subheader("จำนวนความเสี่ยงแยกตามหน่วยงาน")
unit_sum = df_f.groupby('4.หน่วยงานที่ทำให้เกิดความเสี่ยง').size().reset_index(name='count')
st.plotly_chart(px.bar(unit_sum, x='4.หน่วยงานที่ทำให้เกิดความเสี่ยง', y='count', color_discrete_sequence=['#1f77b4']), use_container_width=True)

# --- เริ่มต้นส่วนคำนวณที่ปรับปรุงใหม่ ---

# 1. รวบรวมความเสี่ยงย่อยและนับความถี่ (ไม่แยกหน่วยงาน)
risk_cols = [c for c in df.columns if 'ระบุความเสี่ยงย่อย' in c]
melted = df_f.melt(value_vars=risk_cols, value_name='Risk_Detail').dropna(subset=['Risk_Detail'])
melted = melted[melted['Risk_Detail'] != '']

if not melted.empty:
    matrix_df = melted.groupby('Risk_Detail').size().reset_index(name='Frequency')

    # 2. ฟังก์ชันดึง Severity ที่ปลอดภัย
    def get_sev_from_row(risk_name):
        sev_col = [c for c in df_f.columns if 'ระดับความรุนแรงทางคลินิก' in c]
        if not sev_col: return 'A'
        matches = df_f[df_f.isin([risk_name]).any(axis=1)]
        return matches[sev_col[0]].iloc[0] if not matches.empty else 'A'

    # 3. คำนวณคะแนน
    matrix_df['Sev_Raw'] = matrix_df['Risk_Detail'].apply(get_sev_from_row)
    matrix_df['Freq_Score'] = matrix_df['Frequency'].apply(get_freq_score)
    matrix_df['Sev_Score'] = matrix_df['Sev_Raw'].apply(get_sev_score)
    matrix_df['Risk_Matrix'] = matrix_df['Freq_Score'] * matrix_df['Sev_Score']
    matrix_df = matrix_df.sort_values('Risk_Matrix', ascending=False)

    # 4. แสดงผลตาราง (พร้อมเช็คความปลอดภัย)
    st.subheader("ตาราง Risk Matrix (รวมความเสี่ยงย่อย)")
    st.dataframe(matrix_df[['Risk_Detail', 'Frequency', 'Freq_Score', 'Sev_Score', 'Risk_Matrix']], use_container_width=True)

    # 5. แสดงผลแผนภูมิ
    # --- ส่วนการสร้างสีและระดับความเสี่ยง ---
def get_risk_level(score):
    if score >= 7: return 'สูงมาก (สีแดง)'
    elif score >= 5: return 'สูง (สีส้ม)'
    elif score >= 4: return 'ปานกลาง (สีเหลือง)'
    else: return 'ต่ำ (สีเขียว)'

# เพิ่มคอลัมน์สีและระดับเข้าไปในตาราง
matrix_df['Risk_Level'] = matrix_df['Risk_Matrix'].apply(get_risk_level)
color_map = {
    'สูงมาก (สีแดง)': '#FF0000',
    'สูง (สีส้ม)': '#FFA500',
    'ปานกลาง (สีเหลือง)': '#FFFF00',
    'ต่ำ (สีเขียว)': '#008000'
}

# --- ส่วนการแสดงผล Visualization ---
st.subheader("Risk Matrix Visualization")
fig = px.scatter(
    matrix_df, 
    x='Freq_Score', 
    y='Sev_Score', 
    size='Frequency', 
    color='Risk_Level',  # ใช้ระดับความเสี่ยงในการแบ่งสี
    color_discrete_map=color_map, # กำหนดสีตามเกณฑ์
    hover_name='Risk_Detail',
    range_x=[0.5, 4.5], 
    range_y=[0.5, 4.5]
)

# เพิ่มเส้นตารางหรือรายละเอียดความสวยงาม
fig.update_layout(
    xaxis=dict(tickmode='linear'),
    yaxis=dict(tickmode='linear')
)
st.plotly_chart(fig, use_container_width=True)

# --- สิ้นสุดส่วนคำนวณที่ปรับปรุงใหม่ ---