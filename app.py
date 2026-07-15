import streamlit as st
import pandas as pd
import plotly.express as px

# 1. ตั้งค่าหน้า Dashboard
st.set_page_config(layout="wide")
st.title("🏥 Dashboard ติดตามความเสี่ยงทางห้องปฏิบัติการ")

# --- โหลดและเตรียมข้อมูล (ปรับ path ไฟล์ตามจริง) ---
# แก้ไขส่วน load_data() ให้ใช้ URL แทนไฟล์ .xlsx
@st.cache_data
def load_data():
    # ใช้ลิงก์ CSV ที่ได้จากการ Publish to web
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS8i7qAIxzDWkWCEnZZEjn8xLY8PT7edgUuTtEsh6aMjBHbj2qo-By5X7LxB1VjMovP9U-FUOkupWUm/pub?output=csv" 
    df = pd.read_csv(url) 
    # ตรวจสอบชื่อคอลัมน์วันที่และแปลงเป็น datetime
    df['Date'] = pd.to_datetime(df['1.วันที่เกิดความเสี่ยง'], dayfirst=True)
    return df

df = load_data()

# --- ฟังก์ชันคำนวณคะแนนตามโจทย์ ---
def get_freq_score(count):
    if count > 10: return 4
    elif count >= 5: return 3
    elif count >= 1: return 2
    else: return 1

def get_severity_score(sev_text):
    text = str(sev_text).upper()
    if any(x in text for x in ['G', 'H', 'I']): return 4
    elif any(x in text for x in ['E', 'F']): return 3
    elif any(x in text for x in ['C', 'D']): return 2
    else: return 1 # A-B

# --- Sidebar Filters ---
st.sidebar.header("เครื่องมือสืบค้น")
year = st.sidebar.multiselect("เลือกปี", df['Date'].dt.year.unique())
quarter = st.sidebar.multiselect("เลือกไตรมาส", [1, 2, 3, 4])
risk_type = st.sidebar.multiselect("ประเภทความเสี่ยง", df['5.ประเภทความเสี่ยง'].unique())
unit = st.sidebar.multiselect("หน่วยงาน", df['4.หน่วยงานที่ทำให้เกิดความเสี่ยง'].unique())

# กรองข้อมูล
df_f = df.copy()
if year: df_f = df_f[df_f['Date'].dt.year.isin(year)]
if quarter: df_f = df_f[df_f['Date'].dt.quarter.isin(quarter)]
if risk_type: df_f = df_f[df_f['5.ประเภทความเสี่ยง'].isin(risk_type)]
if unit: df_f = df_f[df_f['4.หน่วยงานที่ทำให้เกิดความเสี่ยง'].isin(unit)]

# --- สรุปภาพรวมรายหน่วยงาน ---
st.subheader("สรุปความเสี่ยงรายหน่วยงาน")
unit_count = df_f.groupby('4.หน่วยงานที่ทำให้เกิดความเสี่ยง').size().reset_index(name='จำนวน')
st.bar_chart(unit_count.set_index('4.หน่วยงานที่ทำให้เกิดความเสี่ยง'))

# --- คำนวณ Risk Matrix ---
# รวมความเสี่ยงย่อยจากคอลัมน์ N, O, P
risk_cols = ['ระบุความเสี่ยงย่อย (Pre-analytical)', ' ระบุความเสี่ยงย่อย (Analytical)', 'ระบุความเสี่ยงย่อย (Post-analytical)']
df_melted = df_f.melt(value_vars=risk_cols, value_name='Risk_Detail')
df_melted = df_melted[df_melted['Risk_Detail'].notna() & (df_melted['Risk_Detail'] != '')]

# คำนวณความถี่และ severity
summary = df_melted.groupby('Risk_Detail').size().reset_index(name='Frequency')
summary['Freq_Score'] = summary['Frequency'].apply(get_freq_score)
summary['Sev_Score'] = df_f.groupby(level=0)['2.2   ระดับความรุนแรงทางคลินิก (Severity)'].first().iloc[0] # ตัวอย่างการดึงค่า
summary['Sev_Score'] = summary['Risk_Detail'].apply(lambda x: get_severity_score(df_f[df_f.isin([x]).any(axis=1)]['2.2   ระดับความรุนแรงทางคลินิก (Severity)'].iloc[0]))
summary['Matrix_Score'] = summary['Freq_Score'] * summary['Sev_Score']
summary = summary.sort_values('Matrix_Score', ascending=False)

# --- แสดงตาราง Risk Matrix ---
st.subheader("ตาราง Risk Matrix")
st.dataframe(summary)

st.subheader("Visualization")
fig = px.scatter(summary, x='Freq_Score', y='Sev_Score', size='Frequency', color='Matrix_Score', hover_name='Risk_Detail')
st.plotly_chart(fig)