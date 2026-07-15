import streamlit as st
import pandas as pd
import plotly.express as px

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

# 3. คำนวณ Risk Matrix (ข้อ 4 และ 5)
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

# รวมความเสี่ยงย่อย (Pre/Analytical/Post)
# --- แก้ไขส่วนรวมความเสี่ยงย่อยตรงนี้ ---

# ใช้การค้นหาชื่อคอลัมน์ที่มีคำว่า "ระบุความเสี่ยงย่อย" เพื่อป้องกันปัญหาเว้นวรรค
risk_cols = [col for col in df.columns if 'ระบุความเสี่ยงย่อย' in col]

# รวมความเสี่ยงย่อยเข้าด้วยกัน
melted = df_f.melt(value_vars=risk_cols, value_name='Risk_Detail').dropna(subset=['Risk_Detail'])
melted = melted[melted['Risk_Detail'] != '']

# นับความถี่รวม (ไม่แยกหน่วยงาน)
matrix_df = melted.groupby('Risk_Detail').size().reset_index(name='Frequency')

# ดึงค่า Severity (ถ้าค่าไม่พบ ให้ใช้ระดับ 1 เป็นค่าเริ่มต้น)
def get_sev_from_row(risk_name):
    matches = df_f[df_f.isin([risk_name]).any(axis=1)]
    if not matches.empty:
        # ดึงค่าจากคอลัมน์ระดับความรุนแรง (รหัสคอลัมน์ R ตามตาราง)
        return matches['2.2   ระดับความรุนแรงทางคลินิก (Severity)'].iloc[0]
    return 'A'

matrix_df['Sev_Raw'] = matrix_df['Risk_Detail'].apply(get_sev_from_row)

# แสดงผล
st.subheader("ตาราง Risk Matrix (รวมความเสี่ยงย่อย)")
st.dataframe(matrix_df[['Risk_Detail', 'Frequency', 'Freq_Score', 'Sev_Score', 'Risk_Matrix']], use_container_width=True)

st.subheader("Risk Matrix Visualization")
st.plotly_chart(px.scatter(matrix_df, x='Freq_Score', y='Sev_Score', size='Frequency', color='Risk_Matrix', hover_name='Risk_Detail'), use_container_width=True)