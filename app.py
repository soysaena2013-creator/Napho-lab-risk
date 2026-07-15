import streamlit as st
import pandas as pd
import plotly.express as px

# 1. ตั้งค่าหน้าเว็บ
st.set_page_config(layout="wide")
st.title("🏥 Dashboard ติดตามความเสี่ยงห้องปฏิบัติการ")

# --- โหลดข้อมูล (ปรับแก้ path ให้ตรงกับไฟล์ของคุณ) ---
# df = pd.read_csv("your_appsheet_data.csv") 

# --- ฟังก์ชันคำนวณคะแนน ---
def get_freq_score(count):
    if count > 10: return 4
    elif count >= 5: return 3
    elif count >= 1: return 2
    else: return 1

def get_severity_score(severity_text):
    text = str(severity_text).upper()
    if any(x in text for x in ['G', 'H', 'I']): return 4
    elif any(x in text for x in ['E', 'F']): return 3
    elif any(x in text for x in ['C', 'D']): return 2
    else: return 1 # A-B

# --- Sidebar Filters ---
st.sidebar.header("Filter")
# สมมติชื่อคอลัมน์จาก AppSheet
df['Date'] = pd.to_datetime(df['Timestamp'])
year = st.sidebar.multiselect("เลือกปี", df['Date'].dt.year.unique())
quarter = st.sidebar.multiselect("เลือกไตรมาส", [1, 2, 3, 4])
risk_type = st.sidebar.multiselect("ประเภทความเสี่ยง", df['ประเภทความเสี่ยง'].unique())
unit = st.sidebar.multiselect("หน่วยงาน", df['4.หน่วยงานที่ทำให้เกิดความเสี่ยง'].unique())

# กรองข้อมูล
df_filtered = df.copy()
if year: df_filtered = df_filtered[df_filtered['Date'].dt.year.isin(year)]
if quarter: df_filtered = df_filtered[df_filtered['Date'].dt.quarter.isin(quarter)]
if risk_type: df_filtered = df_filtered[df_filtered['ประเภทความเสี่ยง'].isin(risk_type)]
if unit: df_filtered = df_filtered[df_filtered['4.หน่วยงานที่ทำให้เกิดความเสี่ยง'].isin(unit)]

# --- ส่วนที่ 1: แผนภูมิสรุปตามหน่วยงาน ---
unit_summary = df_filtered.groupby('4.หน่วยงานที่ทำให้เกิดความเสี่ยง').size().reset_index(name='count')
st.subheader("จำนวนความเสี่ยงแยกตามหน่วยงาน")
fig_bar = px.bar(unit_summary, x='4.หน่วยงานที่ทำให้เกิดความเสี่ยง', y='count')
st.plotly_chart(fig_bar, use_container_width=True)

# --- ส่วนที่ 2: คำนวณ Risk Matrix (รวมความเสี่ยงย่อย) ---
sev_col = [c for c in df.columns if 'ระดับความรุนแรงทางคลินิก' in c][0]
risk_cols = [c for c in df.columns if 'ระบุความเสี่ยงย่อย' in c]

df_melted = df_filtered.melt(id_vars=[sev_col], value_vars=risk_cols, value_name='Risk_Detail')
df_melted = df_melted[df_melted['Risk_Detail'].notna() & (df_melted['Risk_Detail'] != '')]

risk_summary = df_melted.groupby(['Risk_Detail']).agg(
    Frequency=('Risk_Detail', 'count'),
    Severity_Raw=(sev_col, lambda x: x.iloc[0])
).reset_index()

risk_summary['Freq_Score'] = risk_summary['Frequency'].apply(get_freq_score)
risk_summary['Sev_Score'] = risk_summary['Severity_Raw'].apply(get_severity_score)
risk_summary['Risk_Matrix'] = risk_summary['Freq_Score'] * risk_summary['Sev_Score']
risk_summary = risk_summary.sort_values(by='Risk_Matrix', ascending=False)

# --- ส่วนที่ 3: แสดงผลตารางและ Matrix ---
st.markdown("---")
st.subheader("ตารางสรุป Risk Matrix (รวมทุกหน่วยงาน)")
st.dataframe(risk_summary[['Risk_Detail', 'Frequency', 'Freq_Score', 'Sev_Score', 'Risk_Matrix']], 
             use_container_width=True, hide_index=True, height=200)

st.subheader("Risk Matrix Visualization")
fig_matrix = px.scatter(risk_summary, x="Freq_Score", y="Sev_Score", size="Frequency", 
                        color="Risk_Matrix", hover_name="Risk_Detail",
                        range_x=[0.5, 4.5], range_y=[0.5, 4.5])
st.plotly_chart(fig_matrix, use_container_width=True)