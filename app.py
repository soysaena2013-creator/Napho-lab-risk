import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io

# ลงทะเบียนฟอนต์ภาษาไทย (ต้องมีไฟล์ .ttf ในเครื่อง หรือใช้ฟอนต์ที่รองรับ)
# หากไม่ได้เตรียมไฟล์ฟอนต์ไทยไว้ PDF จะไม่แสดงผลภาษาไทยครับ
# แนะนำให้ใช้ฟอนต์ THSarabunNew.ttf
# pdfmetrics.registerFont(TTFont('THSarabun', 'THSarabunNew.ttf'))

# --- ฟังก์ชันสนับสนุน ---
def get_risk_level(score):
    if score >= 7: return 'สูงมาก (สีแดง)'
    elif score >= 5: return 'สูง (สีส้ม)'
    elif score >= 4: return 'ปานกลาง (สีเหลือง)'
    else: return 'ต่ำ (สีเขียว)'

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

# 2. Sidebar Filters
st.sidebar.header("เครื่องมือสืบค้น")
year = st.sidebar.multiselect("เลือกปี", sorted(df['Date'].dt.year.unique()))
quarter = st.sidebar.multiselect("เลือกไตรมาส", [1, 2, 3, 4])

month_names = {1: "มกราคม", 2: "กุมภาพันธ์", 3: "มีนาคม", 4: "เมษายน", 5: "พฤษภาคม", 6: "มิถุนายน", 7: "กรกฎาคม", 8: "สิงหาคม", 9: "กันยายน", 10: "ตุลาคม", 11: "พฤศจิกายน", 12: "ธันวาคม"}
available_months = sorted(df['Date'].dt.month.unique())
month_options = {month_names[m]: m for m in available_months}
selected_month_names = st.sidebar.multiselect("เลือกเดือน", list(month_options.keys()))
selected_months = [month_options[m] for m in selected_month_names]

risk_type = st.sidebar.multiselect("ประเภทความเสี่ยง", df['5.ประเภทความเสี่ยง'].unique())
unit = st.sidebar.multiselect("หน่วยงาน", df['4.หน่วยงานที่ทำให้เกิดความเสี่ยง'].unique())

df_f = df.copy()
if year: df_f = df_f[df_f['Date'].dt.year.isin(year)]
if quarter: df_f = df_f[df_f['Date'].dt.quarter.isin(quarter)]
if selected_months: df_f = df_f[df_f['Date'].dt.month.isin(selected_months)]
if risk_type: df_f = df_f[df_f['5.ประเภทความเสี่ยง'].isin(risk_type)]
if unit: df_f = df_f[df_f['4.หน่วยงานที่ทำให้เกิดความเสี่ยง'].isin(unit)]

st.title("🏥 Dashboard ติดตามความเสี่ยงทางห้องปฏิบัติการ")

# --- ฟังก์ชัน Export PDF ---
def create_pdf(dataframe):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.drawString(100, 800, "Report: Risk Incident Summary")
    # เพิ่มตารางหรือข้อมูลสรุปที่นี่
    c.save()
    buffer.seek(0)
    return buffer

if st.sidebar.button("ดาวน์โหลดรายงานสรุป (PDF)"):
    pdf_file = create_pdf(df_f)
    st.sidebar.download_button("คลิกเพื่อดาวน์โหลด", data=pdf_file, file_name="Risk_Report.pdf", mime="application/pdf")

# --- แผนภูมิและตาราง (เหมือนเดิมของคุณ) ---
st.subheader("จำนวนความเสี่ยงแยกตามหน่วยงานและรูปแบบเหตุการณ์")
matched_cols = [c for c in df_f.columns if 'รูปแบบเหตุการณ์' in str(c)]
if matched_cols and not df_f.empty:
    col_name = matched_cols[0]
    bar_df = df_f.groupby(['4.หน่วยงานที่ทำให้เกิดความเสี่ยง', col_name]).size().reset_index(name='count')
    st.plotly_chart(px.bar(bar_df, x='4.หน่วยงานที่ทำให้เกิดความเสี่ยง', y='count', color=col_name, barmode='group', text_auto=True), use_container_width=True)

st.subheader("ตารางสรุปสถิติอุบัติการณ์ (Miss vs Near Miss)")
if matched_cols and not df_f.empty:
    stats_df = df_f.groupby(['4.หน่วยงานที่ทำให้เกิดความเสี่ยง', col_name]).size().unstack(fill_value=0)
    stats_df['รวม'] = stats_df.sum(axis=1)
    st.dataframe(stats_df, use_container_width=True)

# --- Risk Matrix (เหมือนเดิมของคุณ) ---
risk_cols = [c for c in df.columns if 'ระบุความเสี่ยงย่อย' in c]
melted = df_f.melt(value_vars=risk_cols, value_name='Risk_Detail').dropna(subset=['Risk_Detail'])
if not melted.empty:
    matrix_df = melted.groupby('Risk_Detail').size().reset_index(name='Frequency')
    
    def get_sev_from_row(risk_name):
        sev_col = [c for c in df_f.columns if 'ระดับความรุนแรงทางคลินิก' in c]
        if not sev_col: return 'A'
        matches = df_f[df_f.isin([risk_name]).any(axis=1)]
        return matches[sev_col[0]].iloc[0] if not matches.empty else 'A'

    matrix_df['Sev_Raw'] = matrix_df['Risk_Detail'].apply(get_sev_from_row)
    matrix_df['Freq_Score'] = matrix_df['Frequency'].apply(get_freq_score)
    matrix_df['Sev_Score'] = matrix_df['Sev_Raw'].apply(get_sev_score)
    matrix_df['Risk_Matrix'] = matrix_df['Freq_Score'] * matrix_df['Sev_Score']
    matrix_df['Risk_Level'] = matrix_df['Risk_Matrix'].apply(get_risk_level)
    
    st.subheader("ตาราง Risk Matrix (สรุปรายความเสี่ยงย่อย)")
    st.dataframe(matrix_df, use_container_width=True)