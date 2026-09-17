import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import io
import requests
from fpdf import FPDF
import tempfile
import os
from datetime import datetime

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

def get_thai_budget_year(date):
    if pd.isnull(date): return None
    if date.month >= 10:
        return date.year + 543 + 1
    else:
        return date.year + 543

# ----------------------------------------------------
st.set_page_config(layout="wide")

# --- กำหนด Session State สำหรับเก็บประวัติการทบทวนความเสี่ยง ---
if 'saved_capa_reports' not in st.session_state:
    st.session_state['saved_capa_reports'] = []

# 1. โหลดข้อมูลผ่าน requests และ io.BytesIO เพื่อรองรับภาษาไทยและป้องกัน Error การเข้ารหัส
@st.cache_data(ttl=1)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS8i7qAIxzDWkWCEnZZEjn8xLY8PT7edgUuTtEsh6aMjBHbj2qo-By5X7LxB1VjMovP9U-FUOkupWUm/pub?output=csv"
    try:
        response = requests.get(url)
        response.raise_for_status()
        df = pd.read_csv(io.BytesIO(response.content))
    except Exception as e:
        st.error(f"ไม่สามารถโหลดข้อมูลจากลิงก์ได้: {e}")
        return pd.DataFrame()
    
    df.columns = df.columns.str.strip()
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace('nan', np.nan)
        
    df['Date'] = pd.to_datetime(df['1.วันที่เกิดความเสี่ยง'], dayfirst=True, errors='coerce')
    df['Thai_Budget_Year'] = df['Date'].apply(get_thai_budget_year)
    return df

df = load_data()

# 2. Sidebar Filters & Controls
st.sidebar.header("เครื่องมือสืบค้น")

if st.sidebar.button("🔄 โหลดข้อมูลใหม่ทันที"):
    st.cache_data.clear()
    st.rerun()

if not df.empty:
    available_budget_years = sorted([int(y) for y in df['Thai_Budget_Year'].dropna().unique()], reverse=True)
    selected_budget_years = st.sidebar.multiselect("เลือกปีงบประมาณ (ไทย)", available_budget_years)

    quarter = st.sidebar.multiselect("เลือกไตรมาส", [1, 2, 3, 4])

    month_names = {
        1: "มกราคม", 2: "กุมภาพันธ์", 3: "มีนาคม", 4: "เมษายน",
        5: "พฤษภาคม", 6: "มิถุนายน", 7: "กรกฎาคม", 8: "สิงหาคม",
        9: "กันยายน", 10: "ตุลาคม", 11: "พฤศจิกายน", 12: "ธันวาคม"
    }
    available_months = sorted(df['Date'].dt.month.dropna().unique())
    month_options = {month_names[int(m)]: m for m in available_months if int(m) in month_names}
    selected_month_names = st.sidebar.multiselect("เลือกเดือน", list(month_options.keys()))
    selected_months = [month_options[m] for m in selected_month_names]

    risk_type = st.sidebar.multiselect("ประเภทความเสี่ยง", df['5.ประเภทความเสี่ยง'].dropna().unique())
    unit = st.sidebar.multiselect("หน่วยงาน", df['4.หน่วยงานที่ทำให้เกิดความเสี่ยง'].dropna().unique())

    df_f = df.copy()
    if selected_budget_years: df_f = df_f[df_f['Thai_Budget_Year'].isin(selected_budget_years)]
    if quarter: df_f = df_f[df_f['Date'].dt.quarter.isin(quarter)]
    if selected_months: df_f = df_f[df_f['Date'].dt.month.isin(selected_months)]
    if risk_type: df_f = df_f[df_f['5.ประเภทความเสี่ยง'].isin(risk_type)]
    if unit: df_f = df_f[df_f['4.หน่วยงานที่ทำให้เกิดความเสี่ยง'].isin(unit)]
else:
    df_f = pd.DataFrame()

# --- แสดงประวัติการทบทวนที่บันทึกไว้ใน Sidebar ---
st.sidebar.markdown("---")
st.sidebar.subheader("📂 ประวัติการทบทวนความเสี่ยง (CAPA)")
if len(st.session_state['saved_capa_reports']) > 0:
    for idx, report in enumerate(st.session_state['saved_capa_reports']):
        with st.sidebar.expander(f"🔹 {idx+1}. {report['risk_name'][:25]}..."):
            st.write(f"**ระดับ:** {report['risk_lvl']}")
            st.write(f"**บันทึกเมื่อ:** {report['timestamp']}")
            
            def generate_capa_pdf_from_history(r):
                pdf = FPDF(orientation='P', unit='mm', format='A4')
                pdf.set_auto_page_break(auto=True, margin=15)
                pdf.add_page()
                
                font_path = "Sarabun-Regular.ttf"
                if os.path.exists(font_path):
                    pdf.add_font("Sarabun", "", font_path)
                    pdf.set_font("Sarabun", size=14)
                else:
                    pdf.set_font("Arial", size=14)

                pdf.cell(0, 8, txt="รายงานการทบทวนความเสี่ยงและมาตรการป้องกันแก้ไข (CAPA Report)", ln=True, align='C')
                pdf.set_font("Sarabun", size=10) if os.path.exists(font_path) else pdf.set_font("Arial", size=10)
                pdf.cell(0, 6, txt="ระบบบริหารจัดการความเสี่ยงมาตรฐานห้องปฏิบัติการ (ISO 15189)", ln=True, align='C')
                pdf.ln(5)

                pdf.set_font("Sarabun", size=12) if os.path.exists(font_path) else pdf.set_font("Arial", size=12)
                pdf.cell(0, 7, txt=f"รายการความเสี่ยง: {r['risk_name']}", ln=True)
                pdf.cell(0, 7, txt=f"ระดับความเสี่ยง: {r['risk_lvl']}", ln=True)
                pdf.ln(3)

                pdf.set_fill_color(230, 240, 250)
                pdf.cell(0, 8, txt="  1. การวิเคราะห์สาเหตุ (Root Cause Analysis - ก้างปลา 5M1E)", ln=True, fill=True)
                pdf.set_font("Sarabun", size=10) if os.path.exists(font_path) else pdf.set_font("Arial", size=10)
                pdf.multi_cell(0, 6, txt=f"- บุคลากร (Man): {r['man']}\n- เครื่องมือ (Machine): {r['machine']}\n- วัสดุ/สารเคมี (Material): {r['material']}\n- กระบวนการ (Method): {r['method']}\n- สิ่งแวดล้อม (Environment): {r['env']}")
                pdf.ln(3)

                pdf.set_font("Sarabun", size=12) if os.path.exists(font_path) else pdf.set_font("Arial", size=12)
                pdf.set_fill_color(230, 240, 250)
                pdf.cell(0, 8, txt="  2. แนวทางแก้ไขและป้องกัน (CAPA)", ln=True, fill=True)
                pdf.set_font("Sarabun", size=10) if os.path.exists(font_path) else pdf.set_font("Arial", size=10)
                pdf.multi_cell(0, 6, txt=f"- มาตรการแก้ไขเฉพาะหน้า: {r['corr_act']}\n- มาตรการป้องกันระยะยาว: {r['prev_act']}")
                
                tmp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                pdf.output(tmp_pdf.name)
                return tmp_pdf.name

            hist_pdf_path = generate_capa_pdf_from_history(report)
            with open(hist_pdf_path, "rb") as f:
                st.sidebar.download_button(
                    label=f"📥 ดาวน์โหลด PDF #{idx+1}",
                    data=f,
                    file_name=f"CAPA_History_{idx+1}.pdf",
                    mime="application/pdf",
                    key=f"dl_hist_{idx}"
                )
    
    if st.sidebar.button("🗑️ ล้างประวัติทั้งหมด"):
        st.session_state['saved_capa_reports'] = []
        st.rerun()
else:
    st.sidebar.info("ยังไม่มีประวัติการบันทึกทบทวนความเสี่ยง")

st.title("🏥 Dashboard ติดตามความเสี่ยงทางห้องปฏิบัติการ")

# --- ฟังก์ชันสร้างรายงานตาราง PDF สรุปภาพรวม ---
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
        try: urllib.request.urlretrieve(font_url, font_path)
        except: pass

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
        if solve_val == '-' or solve_val == 'nan':
            for col in dataframe.columns:
                if any(k in str(col) for k in ['แก้ไข', 'การจัดการเบื้องต้น', 'Action']) and 'ปัญหา' not in str(col) and 'เฉพาะหน้า' not in str(col):
                    solve_val = str(row.get(col, '-'))
                    break

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

        row_data = [str(idx+1), date_str, unit_name, shift_val, risk_desc, prob_val, level_val, cause_val, immediate_fix_val, solve_val, result_val, impact_val]

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
st.sidebar.subheader("ออกรายงานภาพรวม")
if st.sidebar.button("📥 ดาวน์โหลดรายงานตาราง PDF (ข้อมูลครบถ้วน)"):
    try:
        pdf_path = generate_pdf_table(df_f)
        with open(pdf_path, "rb") as f:
            st.sidebar.download_button("คลิกเพื่อบันทึกไฟล์ PDF", f, file_name="Risk_Full_Report.pdf", mime="application/pdf")
    except Exception as e:
        st.sidebar.error(f"สร้าง PDF ไม่สำเร็จ: {e}")

# --- 1. แผนภูมิแท่งแยกตามรายหน่วยงาน ---
st.subheader("📊 จำนวนความเสี่ยงแยกตามรายหน่วยงาน (ความเสี่ยงทางคลินิก [Miss/Near Miss] และ ความเสี่ยงทั่วไป)")
matched_event_cols = [c for c in df_f.columns if 'รูปแบบเหตุการณ์' in str(c)]

if not df_f.empty and '4.หน่วยงานที่ทำให้เกิดความเสี่ยง' in df_f.columns and '5.ประเภทความเสี่ยง' in df_f.columns:
    def get_clean_unit_category(row):
        risk_type = str(row.get('5.ประเภทความเสี่ยง', '')).strip()
        if 'คลินิก' in risk_type:
            if matched_event_cols:
                ev_val = str(row.get(matched_event_cols[0], '')).strip()
                if 'Miss' in ev_val and 'Near' not in ev_val: return 'Miss (ทางคลินิก)'
                elif 'Near Miss' in ev_val: return 'Near Miss (ทางคลินิก)'
            return None 
        else: return 'ความเสี่ยงทั่วไป'

    df_f['Clean_Group'] = df_f.apply(get_clean_unit_category, axis=1)
    clean_bar_df = df_f.dropna(subset=['Clean_Group']).copy()
    bar_df = clean_bar_df.groupby(['4.หน่วยงานที่ทำให้เกิดความเสี่ยง', 'Clean_Group']).size().reset_index(name='count')
    
    color_map = {'Miss (ทางคลินิก)': '#1f77b4', 'Near Miss (ทางคลินิก)': '#aec7e8', 'ความเสี่ยงทั่วไป': '#2ca02c'}
    fig_bar = px.bar(bar_df, x='4.หน่วยงานที่ทำให้เกิดความเสี่ยง', y='count', color='Clean_Group', barmode='stack', text_auto=True, color_discrete_map=color_map)
    fig_bar.update_traces(textangle=0, textposition='inside')
    fig_bar.update_layout(font=dict(family="Tahoma, Sarabun, sans-serif", size=14), xaxis=dict(tickangle=-30, type='category'))
    st.plotly_chart(fig_bar, use_container_width=True)
else:
    st.info("ไม่มีข้อมูลในช่วงเวลาหรือเงื่อนไขที่เลือก")

# --- 2. ตารางสรุปสถิติอุบัติการณ์แยกตามหน่วยงาน ---
st.subheader("ตารางสรุปสถิติอุบัติการณ์แยกตามรายหน่วยงาน")
if not df_f.empty and 'Clean_Group' in df_f.columns:
    stats_df = clean_bar_df.groupby(['4.หน่วยงานที่ทำให้เกิดความเสี่ยง', 'Clean_Group']).size().unstack(fill_value=0)
    stats_df['รวม'] = stats_df.sum(axis=1)
    for col in stats_df.columns:
        if col != 'รวม': stats_df[f'% {col}'] = (stats_df[col] / stats_df['รวม'] * 100).round(2)
    st.dataframe(stats_df, use_container_width=True)
else:
    st.info("ไม่พบข้อมูลสำหรับสร้างตารางสรุปสถิติ")

# --- 3. กราฟเส้นแนวโน้มรายเดือนตลอดปีงบประมาณ (เปรียบเทียบซ้อนปีงบประมาณ) และตารางรายละเอียดประกอบการทบทวน ---
st.markdown("---")
st.subheader("📈 วิเคราะห์และทบทวนความเสี่ยงรายรายการ (Trend & Review)")

risk_cols = [c for c in df.columns if 'ระบุความเสี่ยงย่อย' in c]
melt_id_vars = ['Date', 'Thai_Budget_Year', '4.หน่วยงานที่ทำให้เกิดความเสี่ยง', '5.ประเภทความเสี่ยง', '3.ช่วงเวรที่เกิดความเสี่ยง', 'ปัญหาที่พบ', 'LEVEL', 'สาเหตุเกิดจาก', 'การแก้ไขปัญหาเฉพาะหน้า', 'ผลการแก้ไข', 'ผลกระทบต่อคนไข้']
additional_cols = [c for c in df.columns if any(k in str(c) for k in ['แก้ไข', 'เบื้องต้น', 'จัดการ', 'ปัญหา'])]
for c in additional_cols:
    if c not in melt_id_vars:
        melt_id_vars.append(c)

melt_id_vars = [c for c in melt_id_vars if c in df_f.columns]

if not df_f.empty and risk_cols:
    melted_all = df_f.melt(id_vars=melt_id_vars, value_vars=risk_cols, value_name='Risk_Detail').dropna(subset=['Risk_Detail'])
    melted_all = melted_all[melted_all['Risk_Detail'] != '']
else:
    melted_all = pd.DataFrame()

if not melted_all.empty:
    unique_risks = sorted(melted_all['Risk_Detail'].unique())
    selected_risk_item = st.selectbox("🎯 เลือกรายการความเสี่ยงที่ต้องการเจาะลึกเพื่อทบทวน:", unique_risks)

    if selected_risk_item:
        risk_subset = melted_all[melted_all['Risk_Detail'] == selected_risk_item].copy()
        
        # จัดเรียงลำดับเดือนตามปีงบประมาณ (ต.ค. เป็นเดือนแรก = 1 ถึง ก.ย. = 12)
        def get_budget_month_order(date):
            if pd.isnull(date): return 0
            m = date.month
            return m - 9 if m >= 10 else m + 3

        risk_subset['Budget_Month_Index'] = risk_subset['Date'].apply(get_budget_month_order)
        
        thai_budget_months = {
            1: "ต.ค.", 2: "พ.ย.", 3: "ธ.ค.", 4: "ม.ค.", 
            5: "ก.พ.", 6: "มี.ค.", 7: "เม.ย.", 8: "พ.ค.", 
            9: "มิ.ย.", 10: "ก.ค.", 11: "ส.ค.", 12: "ก.ย."
        }
        risk_subset['Month_Label'] = risk_subset['Budget_Month_Index'].map(thai_budget_months)
        
        # จัดกลุ่มนับข้อมูลตาม ปีงบประมาณ และ เดือนตามปีงบประมาณ
        actual_trend = risk_subset.groupby(['Thai_Budget_Year', 'Budget_Month_Index', 'Month_Label']).size().reset_index(name='Count')
        
        # สร้างโครงสร้างกริดให้ครบทุกเดือน (1-12) สำหรับทุกปีงบประมาณที่มีในข้อมูล
        budget_years_in_subset = sorted(risk_subset['Thai_Budget_Year'].dropna().unique())
        full_grid = []
        for b_year in budget_years_in_subset:
            for idx_m in range(1, 13):
                full_grid.append({
                    'Thai_Budget_Year': int(b_year), 
                    'Budget_Month_Index': idx_m, 
                    'Month_Label': thai_budget_months[idx_m]
                })
        
        grid_df = pd.DataFrame(full_grid)
        merged_trend = pd.merge(grid_df, actual_trend, on=['Thai_Budget_Year', 'Budget_Month_Index', 'Month_Label'], how='left').fillna({'Count': 0})
        merged_trend = merged_trend.sort_values(['Thai_Budget_Year', 'Budget_Month_Index'])
        merged_trend['Year_Label_Str'] = "ปีงบ " + merged_trend['Thai_Budget_Year'].astype(str)
        
        st.markdown(f"**กราฟเส้นแสดงแนวโน้มเปรียบเทียบรายปีงบประมาณ: `{selected_risk_item}`**")
        
        # พล็อตเส้นกราฟซ้อนกันแยกสีตามปีงบประมาณ
        fig_line = px.line(
            merged_trend, 
            x='Month_Label', 
            y='Count', 
            color='Year_Label_Str', 
            markers=True, 
            text='Count',
            labels={'Month_Label': 'เดือน (ปีงบประมาณ)', 'Count': 'จำนวนครั้ง', 'Year_Label_Str': 'ปีงบประมาณ'}
        )
        fig_line.update_traces(textposition="top center", textfont=dict(size=11))
        fig_line.update_layout(
            font=dict(family="Tahoma, Sarabun, sans-serif", size=14), 
            xaxis=dict(type='category', categoryorder='array', categoryorder_array=list(thai_budget_months.values()))
        )
        st.plotly_chart(fig_line, use_container_width=True)

        # ตารางแสดงรายละเอียดอุบัติการณ์เชิงลึก
        st.markdown(f"**📋 รายละเอียดอุบัติการณ์เชิงลึกสำหรับทบทวน: `{selected_risk_item}`**")
        detail_view_df = risk_subset.copy()
        
        display_cols_mapping = {
            'Date': 'วันที่เกิด',
            '4.หน่วยงานที่ทำให้เกิดความเสี่ยง': 'หน่วยงาน',
            '3.ช่วงเวรที่เกิดความเสี่ยง': 'ช่วงเวร',
            'ปัญหาที่พบ': 'ปัญหาที่พบ',
            'สาเหตุเกิดจาก': 'สาเหตุเกิดจาก',
            'การแก้ไขปัญหาเบื้องต้น': 'การแก้ไขเบื้องต้น / การแก้ปัญหาเบื้องต้น',
            'การแก้ไขปัญหาเฉพาะหน้า': 'การแก้ไขปัญหาเฉพาะหน้า',
            'ผลการแก้ไข': 'ผลการแก้ไข',
            'ผลกระทบต่อคนไข้': 'ผลกระทบกับคนไข้'
        }
        
        present_cols = {}
        for col_key, col_label in display_cols_mapping.items():
            if col_key in detail_view_df.columns:
                present_cols[col_key] = col_label
            else:
                for c in detail_view_df.columns:
                    if col_key in str(c):
                        present_cols[c] = col_label
                        break
                        
        if present_cols:
            sub_df_display = detail_view_df[list(present_cols.keys())].rename(columns=present_cols)
            if 'วันที่เกิด' in sub_df_display.columns:
                sub_df_display['วันที่เกิด'] = pd.to_datetime(sub_df_display['วันที่เกิด']).dt.strftime('%Y-%m-%d')
            
            html_table = sub_df_display.to_html(classes='table-custom', index=False, escape=False)
            custom_css = """
            <style>
            .table-custom {
                width: 100% !important;
                border-collapse: collapse;
                font-family: 'Sarabun', 'Tahoma', sans-serif;
                font-size: 14px;
            }
            .table-custom th, .table-custom td {
                border: 1px solid #ddd;
                padding: 8px 12px;
                text-align: left;
                word-break: break-word;
                white-space: normal;
            }
            .table-custom th {
                background-color: #f8f9fa;
                font-weight: bold;
                text-align: center;
            }
            .table-container {
                max-height: 400px;
                overflow-y: auto;
                overflow-x: auto;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                margin-bottom: 20px;
            }
            </style>
            """
            st.markdown(f'<div class="table-container">{custom_css}{html_table}</div>', unsafe_allow_html=True)
        else:
            st.info("ไม่พบคอลัมน์รายละเอียดเพิ่มเติมสำหรับรายการนี้")

# --- 4. ตารางและแผนภูมิ Risk Matrix ---
st.markdown("---")
st.subheader("📋 ตาราง Risk Matrix (สรุปรายความเสี่ยงย่อย)")

if not melted_all.empty:
    matrix_df = melted_all.groupby('Risk_Detail').size().reset_index(name='Frequency')
    
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

    color_emoji = {'สูงมาก (สีแดง)': '🔴 สูงมาก', 'สูง (สีส้ม)': '🟠 สูง', 'ปานกลาง (สีเหลือง)': '🟡 ปานกลาง', 'ต่ำ (สีเขียว)': '🟢 ต่ำ'}
    display_df = matrix_df.copy()
    display_df['ระดับความเสี่ยง'] = display_df['Risk_Level'].map(color_emoji)

    st.dataframe(display_df[['Risk_Detail', 'Frequency', 'Freq_Score', 'Sev_Score', 'Risk_Matrix', 'ระดับความเสี่ยง']].rename(columns={
        'Risk_Detail': 'รายการความเสี่ยงย่อย',
        'Frequency': 'ความถี่',
        'Freq_Score': 'คะแนนความถี่',
        'Sev_Score': 'คะแนนความรุนแรง',
        'Risk_Matrix': 'คะแนนรวม Matrix'
    }), use_container_width=True)

    st.subheader("🗺️ แผนภูมิ Risk Matrix (แสดงชื่อความเสี่ยงย่อย)")
    matrix_df['x_jitter'] = matrix_df['Freq_Score'] + np.random.uniform(-0.05, 0.05, len(matrix_df))
    matrix_df['y_jitter'] = matrix_df['Sev_Score'] + np.random.uniform(-0.05, 0.05, len(matrix_df))

    fig_matrix = px.scatter(
        matrix_df, x='x_jitter', y='y_jitter', size='Frequency', color='Risk_Matrix',
        color_continuous_scale=[[0.0, "#008000"], [0.3, "#FFFF00"], [0.6, "#FFA500"], [1.0, "#FF0000"]],
        hover_name='Risk_Detail', range_x=[0.5, 4.5], range_y=[0.5, 4.5],
        labels={'x_jitter': 'คะแนนความถี่ (Frequency Score)', 'y_jitter': 'คะแนนความรุนแรง (Severity Score)'}
    )
    fig_matrix.update_layout(font=dict(family="Tahoma, Sarabun, sans-serif", size=14))
    st.plotly_chart(fig_matrix, use_container_width=True)

# --- 5. ฟังก์ชันทบทวนความเสี่ยงเฉพาะระดับสูง & บันทึกเก็บประวัติลง Sidebar ---
st.markdown("---")
st.subheader("📝 ฟังก์ชันทบทวนความเสี่ยงระดับสูง (สีส้ม/สีแดง) ค้นหาสาเหตุ (ก้างปลา 5M1E) และจัดทำเอกสารคุณภาพ PDF")

if not melted_all.empty:
    high_risk_df = matrix_df[matrix_df['Risk_Level'].isin(['สูง (สีส้ม)', 'สูงมาก (สีแดง)'])]

    if not high_risk_df.empty:
        high_risk_options = high_risk_df['Risk_Detail'].tolist()
        selected_high_risk = st.selectbox("🚨 เลือกความเสี่ยงระดับสูง (สีส้ม/สีแดง) จากช่วงเวลาที่เลือก เพื่อนำมาทบทวนเชิงลึก:", high_risk_options)

        if selected_high_risk:
            current_row = high_risk_df[high_risk_df['Risk_Detail'] == selected_high_risk].iloc[0]
            st.info(f"📌 **ความเสี่ยงที่เลือก:** {selected_high_risk} | **ระดับความเสี่ยง:** {current_row['Risk_Level']} (คะแนน Matrix: {current_row['Risk_Matrix']})")

            col_rev1, col_rev2 = st.columns(2)
            with col_rev1:
                st.markdown("##### 🔍 1. วิเคราะห์สาเหตุ (Root Cause Analysis - ก้างปลา 5M1E)")
                fish_man = st.text_area("👤 บุคลากร (Man):", "เจ้าหน้าที่เวรปฏิบัติงานต่อเนื่องล้าช้า / การทวนสอบก่อนลงผลไม่รัดกุม", key="input_man")
                fish_machine = st.text_area("⚙️ เครื่องมือ/อุปกรณ์ (Machine):", "ระบบเชื่อมต่อ LIS ขัดข้องชั่วขณะ หรือเครื่องวิเคราะห์แจ้งเตือนช้า", key="input_machine")
                fish_material = st.text_area("🧪 วัสดุ/สารเคมี (Material):", "คุณภาพสิ่งส่งตรวจหรือน้ำยาควบคุมคุณภาพไม่เป็นไปตามกำหนด", key="input_material")
                fish_method = st.text_area("📋 กระบวนการ/ขั้นตอน (Method):", "ขั้นตอน Double Check ก่อนอนุมัติผลยังไม่รัดกุมเพียงพอในช่วงเร่งด่วน", key="input_method")
                fish_env = st.text_area("🌍 สิ่งแวดล้อม (Environment):", "อุณหภูมิ/ความชื้นห้องปฏิบัติการ หรือความแออัดและแสงสว่างหน้างาน", key="input_env")
            
            with col_rev2:
                st.markdown("##### 🛡️ 2. มาตรการแก้ไขและป้องกัน (CAPA)")
                corrective_action = st.text_area("🛠️ มาตรการแก้ไขเฉพาะหน้า (Corrective Action):", "ดึงผลตรวจกลับทันที แจ้งแพทย์ผู้รักษา และตรวจวิเคราะห์ซ้ำด้วยตัวอย่างใหม่", key="input_corr")
                preventive_action = st.text_area("🔒 มาตรการป้องกันระยะยาว (Preventive Action):", "กำหนดให้มีระบบ Mandatory Second Review สำหรับผลผิดปกติ และทบทวน SOP", key="input_prev")

            def generate_capa_pdf(risk_name, risk_lvl, man, machine, material, method, env, corr_act, prev_act):
                pdf = FPDF(orientation='P', unit='mm', format='A4')
                pdf.set_auto_page_break(auto=True, margin=15)
                pdf.add_page()
                
                font_path = "Sarabun-Regular.ttf"
                if os.path.exists(font_path):
                    pdf.add_font("Sarabun", "", font_path)
                    pdf.set_font("Sarabun", size=14)
                else:
                    pdf.set_font("Arial", size=14)

                pdf.cell(0, 8, txt="รายงานการทบทวนความเสี่ยงและมาตรการป้องกันแก้ไข (CAPA Report)", ln=True, align='C')
                pdf.set_font("Sarabun", size=10) if os.path.exists(font_path) else pdf.set_font("Arial", size=10)
                pdf.cell(0, 6, txt="ระบบบริหารจัดการความเสี่ยงมาตรฐานห้องปฏิบัติการ (ISO 15189)", ln=True, align='C')
                pdf.ln(5)

                pdf.set_font("Sarabun", size=12) if os.path.exists(font_path) else pdf.set_font("Arial", size=12)
                pdf.cell(0, 7, txt=f"รายการความเสี่ยง: {risk_name}", ln=True)
                pdf.cell(0, 7, txt=f"ระดับความเสี่ยง: {risk_lvl}", ln=True)
                pdf.ln(3)

                pdf.set_fill_color(230, 240, 250)
                pdf.cell(0, 8, txt="  1. การวิเคราะห์สาเหตุ (Root Cause Analysis - ก้างปลา 5M1E)", ln=True, fill=True)
                pdf.set_font("Sarabun", size=10) if os.path.exists(font_path) else pdf.set_font("Arial", size=10)
                pdf.multi_cell(0, 6, txt=f"- บุคลากร (Man): {man}\n- เครื่องมือ (Machine): {machine}\n- วัสดุ/สารเคมี (Material): {material}\n- กระบวนการ (Method): {method}\n- สิ่งแวดล้อม (Environment): {env}")
                pdf.ln(3)

                pdf.set_font("Sarabun", size=12) if os.path.exists(font_path) else pdf.set_font("Arial", size=12)
                pdf.set_fill_color(230, 240, 250)
                pdf.cell(0, 8, txt="  2. แนวทางแก้ไขและป้องกัน (CAPA)", ln=True, fill=True)
                pdf.set_font("Sarabun", size=10) if os.path.exists(font_path) else pdf.set_font("Arial", size=10)
                pdf.multi_cell(0, 6, txt=f"- มาตรการแก้ไขเฉพาะหน้า: {corr_act}\n- มาตรการป้องกันระยะยาว: {prev_act}")
                
                tmp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                pdf.output(tmp_pdf.name)
                return tmp_pdf.name

            if st.button("💾 บันทึกและออกเอกสารคุณภาพ (PDF) สำหรับเก็บเข้าระบบ"):
                try:
                    report_data = {
                        'risk_name': selected_high_risk,
                        'risk_lvl': current_row['Risk_Level'],
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'man': fish_man,
                        'machine': fish_machine,
                        'material': fish_material,
                        'method': fish_method,
                        'env': fish_env,
                        'corr_act': corrective_action,
                        'prev_act': preventive_action
                    }
                    st.session_state['saved_capa_reports'].append(report_data)

                    pdf_file_path = generate_capa_pdf(
                        selected_high_risk, current_row['Risk_Level'], 
                        fish_man, fish_machine, fish_material, fish_method, fish_env,
                        corrective_action, preventive_action
                    )
                    
                    with open(pdf_file_path, "rb") as f:
                        st.download_button(
                            label="📥 คลิกดาวน์โหลดเอกสาร PDF บันทึกความเสี่ยงนี้",
                            data=f,
                            file_name=f"CAPA_Report_{current_row['Risk_Matrix']}.pdf",
                            mime="application/pdf"
                        )
                    st.success("บันทึกข้อมูลเข้าสู่ระบบเรียบร้อยแล้ว! (คุณสามารถเรียกดูย้อนหลังได้จากเมนูด้านซ้าย Sidebar)")
                    st.rerun()
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาดในการสร้าง PDF: {e}")
    else:
        st.success("✨ ในช่วงเวลาและเงื่อนไขตัวกรองที่เลือก ไม่พบความเสี่ยงระดับสูง (สีส้มหรือสีแดง) ทุกอย่างอยู่ในเกณฑ์มาตรฐานที่ควบคุมได้ครับ!")
else:
    st.info("ไม่พบข้อมูลความเสี่ยงในระบบ")