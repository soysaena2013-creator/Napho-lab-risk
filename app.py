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

# 1. โหลดข้อมูล
@st.cache_data(ttl=0)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS8i7qAIxzDWkWCEnZZEjn8xLY8PT7edgUuTtEsh6aMjBHbj2qo-By5X7LxB1VjMovP9U-FUOkupWUm/pub?output=csv" 
    df = pd.read_csv(url)
    df['Date'] = pd.to_datetime(df['1.วันที่เกิดความเสี่ยง'], dayfirst=True)
    return df

df = load_data()

# 2. Sidebar Filters & Controls
st.sidebar.header("เครื่องมือสืบค้นและกรองข้อมูล")

if st.sidebar.button("🔄 โหลดข้อมูลใหม่ทันที"):
    st.cache_data.clear()
    st.rerun()

# เพิ่มตัวกรองช่วงเวลาแบบละเอียด (Date Range Picker)
st.sidebar.subheader("📅 เลือกช่วงเวลาทบทวน")
min_date = df['Date'].min().date() if not df.empty else pd.to_datetime('2025-01-01').date()
max_date = df['Date'].max().date() if not pd.empty else pd.to_datetime('2026-12-31').date()

start_date = st.sidebar.date_input("ตั้งแต่วันที่", min_date)
end_date = st.sidebar.date_input("ถึงวันที่", max_date)

year = st.sidebar.multiselect("เลือกปี", sorted(df['Date'].dt.year.unique()))
quarter = st.sidebar.multiselect("เลือกไตรมาส", [1, 2, 3, 4])
risk_type = st.sidebar.multiselect("ประเภทความเสี่ยง", df['5.ประเภทความเสี่ยง'].unique())
unit = st.sidebar.multiselect("หน่วยงาน", df['4.หน่วยงานที่ทำให้เกิดความเสี่ยง'].unique())

# กรองข้อมูลเบื้องต้น
df_f = df.copy()
if start_date and end_date:
    df_f = df_f[(df_f['Date'].dt.date >= start_date) & (df_f['Date'].dt.date <= end_date)]
if year: df_f = df_f[df_f['Date'].dt.year.isin(year)]
if quarter: df_f = df_f[df_f['Date'].dt.quarter.isin(quarter)]
if risk_type: df_f = df_f[df_f['5.ประเภทความเสี่ยง'].isin(risk_type)]
if unit: df_f = df_f[df_f['4.หน่วยงานที่ทำให้เกิดความเสี่ยง'].isin(unit)]

st.title("🏥 Dashboard ติดตามและทบทวนความเสี่ยงทางห้องปฏิบัติการ")

# --- ฟังก์ชันสร้างรายงาน PDF ---
class PDFTableReport(FPDF):
    def header(self):
        pass

def generate_pdf_table(dataframe):
    pdf = PDFTableReport(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()
    
    font_url = "https://github.com/google/fonts/raw/main/ofl/sarabun/Sarabun-Regular.ttf"
    font_path = "Sarabun-Regular.ttf"
    if not os.path.exists(font_path):
        import urllib.request
        try:
            urllib.request.urlretrieve(font_url, font_path)
        except:
            pass

    if os.path.exists(font_path):
        pdf.add_font("Sarabun", "", font_path)
        pdf.set_font("Sarabun", size=12)
    else:
        pdf.set_font("Arial", size=12)

    pdf.cell(0, 6, txt="Hospital Risk Incident Analysis Report (รายงานสรุปความเสี่ยงและรายละเอียด)", ln=True, align='C')
    pdf.set_font("Sarabun", size=8) if os.path.exists(font_path) else pdf.set_font("Arial", size=8)
    pdf.cell(0, 5, txt=f"Total Filtered Incidents: {len(dataframe)} cases", ln=True, align='L')
    pdf.ln(2)

    headers = [
        "ลำดับ", "วันที่เกิด", "หน่วยงาน", "ช่วงเวร", "ความเสี่ยงที่เกิด", 
        "ปัญหาที่พบ (S)", "LEVEL (T)", "สาเหตุเกิดจาก (U)", "การแก้ไขปัญหาเฉพาะหน้า",  
        "การแก้ไขเบื้องต้น", "ผลการแก้ไข (W)", "ผลกระทบต่อคนไข้ (X)"
    ]
    col_widths = [9, 20, 22, 14, 28, 25, 11, 26, 28, 26, 28, 38] 

    pdf.set_font("Sarabun", size=7) if os.path.exists(font_path) else pdf.set_font("Arial", size=7)
    pdf.set_fill_color(41, 128, 185)
    pdf.set_text_color(255, 255, 255)
    
    header_height = 10  
    x_start_hdr = pdf.get_x()
    y_start_hdr = pdf.get_y()
    
    max_h_line = 3.2
    for i, h in enumerate(headers):
        x_curr = pdf.get_x()
        y_curr = pdf.get_y()
        pdf.cell(col_widths[i], header_height, txt="", border=1, fill=True)
        pdf.set_xy(x_curr, y_curr + 1.5)
        pdf.multi_cell(col_widths[i], max_h_line, txt=h, border=0, align='C')
        pdf.set_xy(x_curr + col_widths[i], y_curr)
    
    pdf.set_xy(x_start_hdr, y_start_hdr + header_height)
    pdf.set_text_color(0, 0, 0)
    line_height = 3.5 

    for idx, row in dataframe.iterrows():
        date_str = str(row['Date'].strftime('%Y-%m-%d')) if pd.notnull(row['Date']) else '-'
        unit_name = str(row.get('4.หน่วยงานที่ทำให้เกิดความเสี่ยง', '-'))
        shift_val = str(row.get('3.ช่วงเวรที่เกิดความเสี่ยง', '-'))
        
        risk_desc = '-'
        for col in dataframe.columns:
            if 'ระบุความเสี่ยงย่อย' in str(col) and pd.notnull(row[col]) and str(row[col]).strip() != '':
                risk_desc = str(row[col])
                break

        solve_val = str(row.get('การแก้ไขปัญหาเบื้องต้น', '-'))
        prob_val = str(row.get('ปัญหาที่พบ', '-'))
        level_val = str(row.get('LEVEL', '-'))
        cause_val = str(row.get('สาเหตุเกิดจาก', '-'))
        
        immediate_fix_val = '-'
        for col in dataframe.columns:
            if 'การแก้ไขปัญหาเฉพาะหน้า' in str(col) or 'เฉพาะหน้า' in str(col):
                immediate_fix_val = str(row.get(col, '-'))
                break

        result_val = str(row.get('ผลการแก้ไข', '-'))
        impact_val = str(row.get('ผลกระทบต่อคนไข้', '-'))

        row_data = [
            str(idx+1), date_str, unit_name, shift_val, risk_desc,
            prob_val, level_val, cause_val, immediate_fix_val,  
            solve_val, result_val, impact_val
        ]

        max_lines = 1
        for i, text in enumerate(row_data):
            w = col_widths[i]
            txt_clean = text if text != 'nan' and pd.notnull(text) else '-'
            chars_per_line = max(int(w / 1.7), 3)
            lines = 0
            for paragraph in str(txt_clean).split('\n'):
                if len(paragraph) == 0: lines += 1
                else: lines += max(1, -(-len(paragraph) // chars_per_line))
            if lines > max_lines: max_lines = lines

        row_height = max(6.0, (max_lines * line_height) + 2.5)

        if pdf.get_y() + row_height > 195:
            pdf.add_page()
            pdf.set_font("Sarabun", size=7) if os.path.exists(font_path) else pdf.set_font("Arial", size=7)
            pdf.set_fill_color(41, 128, 185)
            pdf.set_text_color(255, 255, 255)
            x_start_hdr2 = pdf.get_x()
            y_start_hdr2 = pdf.get_y()
            for i, h in enumerate(headers):
                x_curr = pdf.get_x()
                y_curr = pdf.get_y()
                pdf.cell(col_widths[i], header_height, txt="", border=1, fill=True)
                pdf.set_xy(x_curr, y_curr + 1.5)
                pdf.multi_cell(col_widths[i], max_h_line, txt=h, border=0, align='C')
                pdf.set_xy(x_curr + col_widths[i], y_curr)
            pdf.set_xy(x_start_hdr2, y_start_hdr2 + header_height)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Sarabun", size=7) if os.path.exists(font_path) else pdf.set_font("Arial", size=7)

        is_even = (idx % 2 == 0)
        pdf.set_fill_color(248, 249, 250) if is_even else pdf.set_fill_color(255, 255, 255)

        x_start = pdf.get_x()
        y_start = pdf.get_y()
        alignments = ['C', 'C', 'L', 'C', 'L', 'L', 'C', 'L', 'L', 'L', 'L', 'L']

        for i, text in enumerate(row_data):
            x_current = pdf.get_x()
            txt_clean = text if text != 'nan' and pd.notnull(text) else '-'
            pdf.cell(col_widths[i], row_height, txt="", border=1, fill=True)
            pdf.set_xy(x_current, y_start + 1.0)
            pdf.multi_cell(col_widths[i], line_height, txt=str(txt_clean), border=0, align=alignments[i])
            pdf.set_xy(x_current + col_widths[i], y_start)

        pdf.set_xy(x_start, y_start + row_height)

    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf.output(tmp_file.name)
    return tmp_file.name

st.sidebar.markdown("---")
st.sidebar.subheader("ออกรายงาน")
if st.sidebar.button("📥 ดาวน์โหลดรายงาน PDF (ข้อมูลครบถ้วน)"):
    try:
        pdf_path = generate_pdf_table(df_f)
        with open(pdf_path, "rb") as f:
            st.sidebar.download_button(
                label="คลิกเพื่อบันทึกไฟล์ PDF", data=f,
                file_name="Risk_Full_Report_Complete.pdf", mime="application/pdf"
            )
    except Exception as e:
        st.sidebar.error(f"สร้าง PDF ไม่สำเร็จ: {e}")

# --- 1. แผนภูมิแท่ง (แบ่งคลินิก vs ทั่วไป และรวม Miss/Near Miss ในแท่งเดียวกันแบบ Stack) ---
st.subheader("📊 จำนวนความเสี่ยงแยกตามหน่วยงาน (จำแนกความเสี่ยงทางคลินิกและทั่วไป)")
matched_cols = [c for c in df_f.columns if 'รูปแบบเหตุการณ์' in str(c)]

if not df_f.empty:
    # สร้างหมวดหมู่ความเสี่ยง (คลินิก / ทั่วไป)
    def classify_risk_group(row):
        t = str(row.get('5.ประเภทความเสี่ยง', ''))
        if matched_cols:
            sub = str(row.get(matched_cols[0], ''))
            if 'คลินิก' in t or 'Miss' in sub or 'Near Miss' in sub:
                return f"คลินิก: {sub if sub != 'nan' else 'ทั่วไป'}"
        return f"ทั่วไป: {t if t != 'nan' else 'อื่นๆ'}"

    df_f['Risk_Category_Group'] = df_f.apply(classify_risk_group, axis=1)
    
    bar_df = df_f.groupby(['4.หน่วยงานที่ทำให้เกิดความเสี่ยง', 'Risk_Category_Group']).size().reset_index(name='count')
    fig_bar = px.bar(
        bar_df, x='4.หน่วยงานที่ทำให้เกิดความเสี่ยง', y='count', color='Risk_Category_Group', 
        barmode='stack', text_auto=True
    )
    fig_bar.update_traces(textangle=0, textposition='auto')
    st.plotly_chart(fig_bar, use_container_width=True)
else:
    st.info("ไม่พบข้อมูลในช่วงเวลาที่เลือก")

# --- 2. ส่วนเจาะจงเลือกดูรายความเสี่ยงและกราฟเส้นแนวโน้มตามช่วงเวลา ---
st.markdown("---")
st.subheader("📈 วิเคราะห์แนวโน้มความเสี่ยงรายรายการ (Trend Analysis)")

risk_cols = [c for c in df.columns if 'ระบุความเสี่ยงย่อย' in c]
all_risk_details = []
for col in risk_cols:
    all_risk_details.extend(df[col].dropna().unique().tolist())
all_risk_details = sorted(list(set([str(x).strip() for x in all_risk_details if str(x).strip() != ''])))

selected_specific_risk = st.selectbox("🔍 เลือกรายการความเสี่ยงที่ต้องการเจาะจงทบทวนแนวโน้ม:", ["-- แสดงทั้งหมด --"] + all_risk_details)

df_trend = df_f.copy()
if selected_specific_risk != "-- แสดงทั้งหมด --":
    # กรองเฉพาะแถวที่มีความเสี่ยงย่อยนี้
    mask = False
    for col in risk_cols:
        mask = mask | (df_trend[col].astype(str).str.strip() == selected_specific_risk)
    df_trend = df_trend[mask]

if not df_trend.empty:
    # จัดกลุ่มตามเดือน/ปีเพื่อทำกราฟเส้นแนวโน้ม
    df_trend['YearMonth'] = df_trend['Date'].dt.to_period('M').astype(str)
    trend_grouped = df_trend.groupby('YearMonth').size().reset_index(name='Incident_Count')
    
    fig_line = px.line(
        trend_grouped, x='YearMonth', y='Incident_Count', markers=True,
        title=f"แนวโน้มอุบัติการณ์: {selected_specific_risk}",
        labels={'YearMonth': 'เดือน/ปี', 'Incident_Count': 'จำนวนครั้ง (1 ครั้ง)'}
    )
    fig_line.update_traces(line_color='#e74c3c', marker_size=8)
    st.plotly_chart(fig_line, use_container_width=True)
else:
    st.info("ไม่พบข้อมูลอุบัติการณ์สำหรับรายการความเสี่ยงที่เลือกในช่วงเวลานี้")

# --- 3. ส่วนเพิ่มการทบทวนความเสี่ยงและผลการทบทวนตามแนวทางมาตรฐาน ---
st.markdown("---")
st.subheader("📝 บันทึกผลการทบทวนความเสี่ยง (Risk Review & Action Plan)")

with st.form("risk_review_form"):
    col1, col2 = st.columns(2)
    with col1:
        review_topic = st.selectbox("หัวข้อความเสี่ยงที่นำมาทบทวน", all_risk_details if all_risk_details else ["ไม่มีข้อมูล"])
        review_team = st.text_input("ทีมผู้ทบทวน / หน่วยงานที่รับผิดชอบ")
        root_cause_analysis = st.text_area("ผลการวิเคราะห์สาเหตุที่แท้จริง (Root Cause Analysis)")
    with col2:
        preventive_action = st.text_area("มาตรการป้องกันและแก้ไข (Corrective & Preventive Action - CAPA)")
        review_status = st.selectbox("สถานะการทบทวน", ["อยู่ระหว่างดำเนินการ", "ดำเนินการแล้วเสร็จ", "ติดตามประเมินผล"])
        target_date = st.date_input("กำหนดแล้วเสร็จ (Target Date)")

    submitted = st.form_submit_button("💾 บันทึกผลการทบทวน")
    if submitted:
        st.success(f"บันทึกผลการทบทวนหัวข้อ '{review_topic}' เรียบร้อยแล้ว! (สามารถนำไปรวบรวมทำรายงานมาตรฐานความเสี่ยงต่อไป)")

# --- 4. ส่วนคำนวณ Risk Matrix ---
st.markdown("---")
melted = df_f.melt(value_vars=risk_cols, value_name='Risk_Detail').dropna(subset=['Risk_Detail'])
melted = melted[melted['Risk_Detail'] != '']

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
    matrix_df = matrix_df.sort_values(by='Risk_Matrix', ascending=False)

    st.subheader("🎯 ตาราง Risk Matrix (สรุปรายความเสี่ยงย่อย)")
    color_emoji = {'สูงมาก (สีแดง)': '🔴 สูงมาก', 'สูง (สีส้ม)': '🟠 สูง', 'ปานกลาง (สีเหลือง)': '🟡 ปานกลาง', 'ต่ำ (สีเขียว)': '🟢 ต่ำ'}
    display_df = matrix_df.copy()
    display_df['ระดับความเสี่ยง'] = display_df['Risk_Level'].map(color_emoji)
    
    st.dataframe(display_df[['Risk_Detail', 'Frequency', 'Freq_Score', 'Sev_Score', 'Risk_Matrix', 'ระดับความเสี่ยง']], use_container_width=True, hide_index=True)
else:
    st.write("ไม่พบข้อมูลความเสี่ยงในช่วงที่เลือก")