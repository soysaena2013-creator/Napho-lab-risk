import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from fpdf import FPDF
import tempfile
import os

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

@st.cache_data
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS8i7qAIxzDWkWCEnZZEjn8xLY8PT7edgUuTtEsh6aMjBHbj2qo-By5X7LxB1VjMovP9U-FUOkupWUm/pub?output=csv" 
    df = pd.read_csv(url)
    df['Date'] = pd.to_datetime(df['1.วันที่เกิดความเสี่ยง'], dayfirst=True)
    return df

df = load_data()

# Sidebar Filters
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

# --- ฟังก์ชันสร้าง PDF ฉบับสมบูรณ์สำหรับวิเคราะห์ ---
def generate_detailed_pdf(dataframe):
    pdf = FPDF()
    pdf.add_page()
    
    font_path = "THSarabunNew.ttf"
    if os.path.exists(font_path):
        pdf.add_font("THSarabun", "", font_path)
        pdf.set_font("THSarabun", size=16)
    else:
        pdf.set_font("Arial", size=12)

    # หัวข้อรายงาน
    pdf.cell(0, 10, txt="Hospital Risk Incident Summary & Analysis Report", ln=True, align='C')
    pdf.ln(5)
    
    pdf.set_font("THSarabun", size=14) if os.path.exists(font_path) else pdf.set_font("Arial", size=10)
    pdf.cell(0, 8, txt=f"Total Filtered Incidents: {len(dataframe)} cases", ln=True, align='L')
    pdf.ln(5)

    # 1. สรุปตามหน่วยงาน
    pdf.cell(0, 8, txt="1. Summary by Department & Incident Type:", ln=True, align='L')
    matched_cols = [c for c in dataframe.columns if 'รูปแบบเหตุการณ์' in str(c)]
    if matched_cols and not dataframe.empty:
        col_name = matched_cols[0]
        summary_df = dataframe.groupby(['4.หน่วยงานที่ทำให้เกิดความเสี่ยง', col_name]).size().reset_index(name='Count')
        for index, row in summary_df.iterrows():
            line_text = f"- [{row['4.หน่วยงานที่ทำให้เกิดความเสี่ยง']}] {row[col_name]}: {row['Count']} cases"
            pdf.cell(0, 7, txt=line_text, ln=True, align='L')
    
    pdf.ln(5)
    # 2. สรุปความเสี่ยงย่อย (Risk Matrix Preview)
    pdf.cell(0, 8, txt="2. Top Risk Details Frequency:", ln=True, align='L')
    risk_cols = [c for c in dataframe.columns if 'ระบุความเสี่ยงย่อย' in c]
    if risk_cols:
        melted = dataframe.melt(value_vars=risk_cols, value_name='Risk_Detail').dropna(subset=['Risk_Detail'])
        melted = melted[melted['Risk_Detail'] != '']
        if not melted.empty:
            top_risks = melted.groupby('Risk_Detail').size().reset_index(name='Frequency').sort_values(by='Frequency', ascending=False).head(5)
            for index, row in top_risks.iterrows():
                pdf.cell(0, 7, txt=f"- {row['Risk_Detail']}: {row['Frequency']} times", ln=True, align='L')

    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf.output(tmp_file.name)
    return tmp_file.name

st.sidebar.markdown("---")
st.sidebar.subheader("ออกรายงานเชิงวิเคราะห์")
if st.sidebar.button("ดาวน์โหลดรายงาน PDF (ฉบับสมบูรณ์)"):
    try:
        pdf_path = generate_detailed_pdf(df_f)
        with open(pdf_path, "rb") as f:
            st.sidebar.download_button(
                label="📥 คลิกดาวน์โหลด PDF",
                data=f,
                file_name="Risk_Analysis_Report.pdf",
                mime="application/pdf"
            )
    except Exception as e:
        st.sidebar.error(f"สร้าง PDF ไม่สำเร็จ: {e}")

# --- แผนภูมิแท่งและตารางแสดงผลบนเว็บตามปกติของคุณ ---
st.subheader("จำนวนความเสี่ยงแยกตามหน่วยงานและรูปแบบเหตุการณ์")
matched_cols = [c for c in df_f.columns if 'รูปแบบเหตุการณ์' in str(c)]

if matched_cols and not df_f.empty:
    col_name = matched_cols[0]
    bar_df = df_f.groupby(['4.หน่วยงานที่ทำให้เกิดความเสี่ยง', col_name]).size().reset_index(name='count')
    fig_bar = px.bar(bar_df, x='4.หน่วยงานที่ทำให้เกิดความเสี่ยง', y='count', color=col_name, barmode='group', text_auto=True)
    st.plotly_chart(fig_bar, use_container_width=True)
else:
    unit_sum = df_f.groupby('4.หน่วยงานที่ทำให้เกิดความเสี่ยง').size().reset_index(name='count')
    st.plotly_chart(px.bar(unit_sum, x='4.หน่วยงานที่ทำให้เกิดความเสี่ยง', y='count', color_discrete_sequence=['#1f77b4'], text_auto=True), use_container_width=True)

st.subheader("ตารางสรุปสถิติอุบัติการณ์ (Miss vs Near Miss)")
if matched_cols and not df_f.empty:
    stats_df = df_f.groupby(['4.หน่วยงานที่ทำให้เกิดความเสี่ยง', col_name]).size().unstack(fill_value=0)
    stats_df['รวม'] = stats_df.sum(axis=1)
    for col in stats_df.columns:
        if col != 'รวม':
            stats_df[f'% {col}'] = (stats_df[col] / stats_df['รวม'] * 100).round(2)
    st.dataframe(stats_df, use_container_width=True)

# Risk Matrix section...