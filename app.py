import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import io
import requests
import matplotlib.pyplot as plt
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

# --- กำหนด Session State สำหรับเก็บประวัติการทบทวนความเสี่ยง และรายชื่อคณะทำงานกลาง ---
if 'saved_capa_reports' not in st.session_state:
    st.session_state['saved_capa_reports'] = []

# กำหนดรายชื่อคณะทำงานกลาง (Master List) ไว้ล่วงหน้า สามารถเพิ่ม/แก้ไขตรงนี้ได้เลยครับ
if 'master_reviewers' not in st.session_state:
    st.session_state['master_reviewers'] = [
        {"name": "พว.สมชาย ใจดี", "position": "นักเทคนิคการแพทย์ชำนาญการ / ผู้จัดการความเสี่ยง", "role": "ผู้ทบทวนความเสี่ยง", "sig_path": None},
        {"name": "ทนม.สมหญิง รักงาน", "position": "นักเทคนิคการแพทย์ปฏิบัติการ", "role": "ผู้ตรวจสอบ", "sig_path": None},
        {"name": "ดร.พญ.สมศรี มีสุข", "position": "หัวหน้ากลุ่มงานพยาธิวิทยาคลินิก", "role": "ผู้อนุมัติ CAPA", "sig_path": None}
    ]

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

# --- ฟังก์ชันช่วยดึงข้อมูลสาเหตุเกิดจาก (U) และ V&AA ---
def extract_cause_values(row, columns_list):
    cause_text = ""
    for col in columns_list:
        col_str = str(col).strip()
        if 'สาเหตุ' in col_str or col_str.startswith('U.') or ' U ' in col_str or col_str == 'U':
            val = str(row.get(col, ''))
            if val and val != 'nan':
                cause_text = val
                break
    if not cause_text or cause_text == 'nan':
        if len(row) > 20 and pd.notnull(row.iloc[20]) and str(row.iloc[20]) != 'nan':
            cause_text = str(row.iloc[20])
    return cause_text if cause_text and cause_text != 'nan' else '-'

def extract_v_aa_values(row, columns_list):
    v_text, aa_text = "", ""
    for col in columns_list:
        col_str = str(col).strip()
        if col_str.startswith('V.') or ' V ' in col_str or col_str == 'V':
            val = str(row.get(col, ''))
            if val and val != 'nan': v_text = val
        elif col_str.startswith('AA.') or ' AA ' in col_str or col_str == 'AA':
            val = str(row.get(col, ''))
            if val and val != 'nan': aa_text = val
    
    if not v_text and not aa_text:
        for idx_col, val_col in enumerate(row):
            col_name = str(columns_list[idx_col])
            if ('แก้ไข' in col_name or 'เบื้องต้น' in col_name) and 'เฉพาะหน้า' not in col_name and 'ผล' not in col_name:
                if pd.notnull(val_col) and str(val_col) != 'nan':
                    v_text = str(val_col)
                    break

    solve_val = " / ".join([x for x in [v_text, aa_text] if x and x != 'nan'])
    return solve_val if solve_val else '-'

# --- แสดงประวัติการทบทวนที่บันทึกไว้ใน Sidebar ---
st.sidebar.markdown("---")
st.sidebar.subheader("📂 ประวัติการทบทวนความเสี่ยง (CAPA)")
if len(st.session_state['saved_capa_reports']) > 0:
    for idx, report in enumerate(st.session_state['saved_capa_reports']):
        with st.sidebar.expander(f"🔹 {idx+1}. {report['risk_name'][:25]}..."):
            st.write(f"**ระดับ:** {report['risk_lvl']}")
            st.write(f"**บันทึกเมื่อ:** {report['timestamp']}")
else:
    st.sidebar.info("ยังไม่มีประวัติการบันทึกทบทวนความเสี่ยง")

st.title("🏥 Dashboard ติดตามความเสี่ยงทางห้องปฏิบัติการ (รพ.นาโพธิ์)")

# --- ฟังก์ชันสร้างรายงานตาราง PDF สรุปภาพรวม ---
class PDFTableReport(FPDF):
    def header(self):
        pass

def generate_pdf_table(dataframe):
    pdf = PDFTableReport(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()
    
    font_path = "Sarabun-Regular.ttf"
    if os.path.exists(font_path):
        pdf.add_font("Sarabun", "", font_path)
        pdf.set_font("Sarabun", size=12)
    else:
        pdf.set_font("Arial", size=12)

    pdf.cell(0, 6, txt="Hospital Risk Incident Analysis Report - รพ.นาโพธิ์", ln=True, align='C')
    pdf.set_font("Sarabun", size=8) if os.path.exists(font_path) else pdf.set_font("Arial", size=8)
    pdf.cell(0, 5, txt=f"Total Filtered Incidents: {len(dataframe)} cases", ln=True, align='L')
    pdf.ln(2)

    headers = [
        "ลำดับ", "วันที่เกิด", "หน่วยงาน", "ช่วงเวร", "ความเสี่ยงที่เกิด", 
        "LEVEL (T)", "สาเหตุเกิดจาก (U)", "การแก้ไขปัญหาเฉพาะหน้า",  
        "การแก้ไขเบื้องต้น (V & AA)", "ผลการแก้ไข (W)", "ผลกระทบต่อคนไข้ (X)"
    ]
    col_widths = [9, 20, 22, 14, 30, 11, 28, 28, 28, 28, 38] 

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

        cause_val = extract_cause_values(row, dataframe.columns)
        solve_val = extract_v_aa_values(row, dataframe.columns)
        level_val = str(row.get('LEVEL', '-'))
        
        immediate_fix_val = '-'
        for col in dataframe.columns:
            if 'การแก้ไขปัญหาเฉพาะหน้า' in str(col) or 'เฉพาะหน้า' in str(col):
                immediate_fix_val = str(row.get(col, '-'))
                break

        result_val = str(row.get('ผลการแก้ไข', '-'))
        impact_val = str(row.get('ผลกระทบต่อคนไข้', '-'))

        row_data = [str(idx+1), date_str, unit_name, shift_val, risk_desc, level_val, cause_val, immediate_fix_val, solve_val, result_val, impact_val]

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
        alignments = ['C', 'C', 'L', 'C', 'L', 'C', 'L', 'L', 'L', 'L', 'L']

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
st.subheader("📊 จำนวนความเสี่ยงแยกตามรายหน่วยงาน")
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

#เตรียม melted_all สำหรับส่วนอื่นๆ
risk_cols = [c for c in df.columns if 'ระบุความเสี่ยงย่อย' in c]
if not df_f.empty and risk_cols:
    melted_all = df_f.melt(id_vars=[c for c in df_f.columns if c not in risk_cols], value_vars=risk_cols, value_name='Risk_Detail').dropna(subset=['Risk_Detail'])
    melted_all = melted_all[melted_all['Risk_Detail'] != '']
else:
    melted_all = pd.DataFrame()

# --- 2. ตารางและแผนภูมิ Risk Matrix ---
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

# --- 3. ฟังก์ชันทบทวนความเสี่ยง และเลือกลายเซ็นจากรายชื่อกลาง ---
st.markdown("---")
st.subheader("📝 ฟังก์ชันทบทวนความเสี่ยงและเลือกรายชื่อผู้ร่วมทบทวน (Master Reviewers List)")

if not melted_all.empty:
    unique_risks = sorted(melted_all['Risk_Detail'].unique())
    selected_risk_item = st.selectbox("🎯 เลือกรายการความเสี่ยงที่ต้องการเจาะลึกเพื่อทบทวน:", unique_risks)

    if selected_risk_item:
        risk_subset = melted_all[melted_all['Risk_Detail'] == selected_risk_item].copy()
        
        def get_budget_month_order(date):
            if pd.isnull(date): return 0
            m = date.month
            return m - 9 if m >= 10 else m + 3

        risk_subset['Budget_Month_Index'] = risk_subset['Date'].apply(get_budget_month_order)
        thai_budget_months = {1: "ต.ค.", 2: "พ.ย.", 3: "ธ.ค.", 4: "ม.ค.", 5: "ก.พ.", 6: "มี.ค.", 7: "เม.ย.", 8: "พ.ค.", 9: "มิ.ย.", 10: "ก.ค.", 11: "ส.ค.", 12: "ก.ย."}
        risk_subset['Month_Label'] = risk_subset['Budget_Month_Index'].map(thai_budget_months)
        
        actual_trend = risk_subset.groupby(['Thai_Budget_Year', 'Budget_Month_Index', 'Month_Label']).size().reset_index(name='Count')
        budget_years_in_subset = sorted(risk_subset['Thai_Budget_Year'].dropna().unique())
        full_grid = [{'Thai_Budget_Year': int(b), 'Budget_Month_Index': m, 'Month_Label': thai_budget_months[m]} for b in budget_years_in_subset for m in range(1, 13)]
        
        grid_df = pd.DataFrame(full_grid)
        merged_trend = pd.merge(grid_df, actual_trend, on=['Thai_Budget_Year', 'Budget_Month_Index', 'Month_Label'], how='left').fillna({'Count': 0})
        merged_trend = merged_trend.sort_values(['Thai_Budget_Year', 'Budget_Month_Index'])
        merged_trend['Year_Label_Str'] = "ปีงบ " + merged_trend['Thai_Budget_Year'].astype(str)
        
        st.markdown(f"**กราฟเส้นแสดงแนวโน้มเปรียบเทียบรายปีงบประมาณ: `{selected_risk_item}`**")
        fig_line = px.line(merged_trend, x='Month_Label', y='Count', color='Year_Label_Str', markers=True, text='Count')
        st.plotly_chart(fig_line, use_container_width=True)

        st.markdown("##### 🏢 สรุปจำนวนความเสี่ยงแยกตามแผนกสำหรับรายการนี้")
        unit_col_name = '4.หน่วยงานที่ทำให้เกิดความเสี่ยง'
        if unit_col_name in risk_subset.columns:
            st.dataframe(risk_subset[unit_col_name].value_counts().reset_index(name='จำนวนครั้ง (เรื่อง)').rename(columns={'index': 'หน่วยงาน/แผนก'}), use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("##### 🔍 วิเคราะห์สาเหตุ (ก้างปลา 5M1E) และจัดทำมาตรการ CAPA")
        
        col_rev1, col_rev2 = st.columns(2)
        with col_rev1:
            fish_man = st.text_area("👤 บุคลากร (Man):", "เจ้าหน้าที่เวรปฏิบัติงานต่อเนื่องล้าช้า / การทวนสอบก่อนลงผลไม่รัดกุม")
            fish_machine = st.text_area("⚙️ เครื่องมือ/อุปกรณ์ (Machine):", "ระบบเชื่อมต่อ LIS ขัดข้องชั่วขณะ หรือเครื่องวิเคราะห์แจ้งเตือนช้า")
            fish_material = st.text_area("🧪 วัสดุ/สารเคมี (Material):", "คุณภาพสิ่งส่งตรวจหรือน้ำยาควบคุมคุณภาพไม่เป็นไปตามกำหนด")
        with col_rev2:
            fish_method = st.text_area("📋 กระบวนการ/ขั้นตอน (Method):", "ขั้นตอน Double Check ก่อนอนุมัติผลยังไม่รัดกุมเพียงพอในช่วงเร่งด่วน")
            fish_env = st.text_area("🌍 สิ่งแวดล้อม (Environment):", "อุณหภูมิ/ความชื้นห้องปฏิบัติการ หรือความแออัดและแสงสว่างหน้างาน")
            
        corrective_action = st.text_area("🛠️ มาตรการแก้ไขเฉพาะหน้า (Corrective Action):", "ดึงผลตรวจกลับทันที แจ้งแพทย์ผู้รักษา และตรวจวิเคราะห์ซ้ำด้วยตัวอย่างใหม่")
        preventive_action = st.text_area("🔒 มาตรการป้องกันระยะยาว (Preventive Action):", "กำหนดให้มีระบบ Mandatory Second Review สำหรับผลผิดปกติ และทบทวน SOP")

        # --- ส่วนเลือกรายชื่อคณะทำงานจากรายชื่อกลาง (Master List) ---
        st.markdown("---")
        st.markdown("##### ✍️ เลือกรายชื่อคณะทำงานผู้ร่วมทบทวนจากรายชื่อกลาง (Master List)")
        st.write("ติ๊กเลือกรายชื่อคณะทำงานที่ต้องการให้ร่วมลงนามในรายงานฉบับนี้:")

        selected_reviewers_for_report = []
        for idx, rev in enumerate(st.session_state['master_reviewers']):
            col_chk, col_up = st.columns([3, 2])
            with col_chk:
                is_selected = st.checkbox(f"**{rev['name']}** ({rev['role']})\n*ตำแหน่ง: {rev['position']}*", value=True, key=f"chk_rev_{idx}")
            with col_up:
                # อนุญาตให้อัปโหลดรูปลายเซ็นเฉพาะบุคคลนั้นๆ เก็บไว้ในระบบกลางได้
                sig_upload = st.file_uploader(f"อัปโหลดลายเซ็นของ {rev['name']}", type=["png", "jpg", "jpeg"], key=f"sig_file_{idx}")
                if sig_upload is not None:
                    tmp_s = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                    tmp_s.write(sig_upload.read())
                    st.session_state['master_reviewers'][idx]['sig_path'] = tmp_s.name

            if is_selected:
                selected_reviewers_for_report.append(st.session_state['master_reviewers'][idx])
            st.markdown("---")

        current_risk_row = matrix_df[matrix_df['Risk_Detail'] == selected_risk_item] if 'matrix_df' in locals() and not matrix_df.empty else pd.DataFrame()
        risk_lvl_val = current_risk_row['Risk_Level'].iloc[0] if not current_risk_row.empty else 'ปานกลาง (สีเหลือง)'

        # --- ฟังก์ชันสร้าง PDF พร้อมฝังโลโก้ และรายชื่อคณะทำงานที่เลือก ---
        def generate_capa_pdf_with_master_list(risk_name, risk_lvl, man, machine, material, method, env, corr_act, prev_act, reviewers, fig_path=None):
            pdf = FPDF(orientation='P', unit='mm', format='A4')
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()
            
            font_path = "Sarabun-Regular.ttf"
            if os.path.exists(font_path):
                pdf.add_font("Sarabun", "", font_path)
                pdf.set_font("Sarabun", size=14)
            else:
                pdf.set_font("Arial", size=14)

            # --- ส่วนหัวรายงาน (แทรกโลโก้ รพ.นาโพธิ์) ---
            logo_url = "https://drive.google.com/uc?export=download&id=1V9sj6Y_W2uR65y86dIXZYc9r2xIzWeYB"
            try:
                logo_resp = requests.get(logo_url)
                if logo_resp.status_code == 200:
                    tmp_logo = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                    tmp_logo.write(logo_resp.content)
                    tmp_logo.close()
                    pdf.image(tmp_logo.name, x=94, y=10, w=22)
                    pdf.ln(18)
            except:
                pass

            pdf.set_font("Sarabun", 'B', 14) if os.path.exists(font_path) else pdf.set_font("Arial", 'B', 14)
            pdf.cell(0, 7, txt="โรงพยาบาลนาโพธิ์ จังหวัดบุรีรัมย์ (Na Pho Hospital)", ln=True, align='C')
            pdf.set_font("Sarabun", size=11) if os.path.exists(font_path) else pdf.set_font("Arial", size=11)
            pdf.cell(0, 6, txt="กลุ่มงานเทคนิคการแพทย์และพยาธิวิทยาคลินิก (ISO 15189 Risk Review)", ln=True, align='C')
            pdf.ln(2)
            
            pdf.set_font("Sarabun", 'B', 12) if os.path.exists(font_path) else pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 7, txt="รายงานการทบทวนความเสี่ยงและมาตรการป้องกันแก้ไข (CAPA Report)", ln=True, align='C')
            pdf.ln(3)

            pdf.set_font("Sarabun", size=10) if os.path.exists(font_path) else pdf.set_font("Arial", size=10)
            pdf.cell(0, 6, txt=f"รายการความเสี่ยง: {risk_name} | ระดับความเสี่ยง: {risk_lvl}", ln=True)
            pdf.ln(3)

            if fig_path and os.path.exists(fig_path):
                pdf.image(fig_path, x=15, w=180)
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
            pdf.ln(8)

            # --- ส่วนลงนามดิจิทัล (แสดงรายชื่อที่เลือกจาก Master List) ---
            pdf.set_font("Sarabun", 'B', 11) if os.path.exists(font_path) else pdf.set_font("Arial", 'B', 11)
            pdf.cell(0, 6, txt="3. ลงนามคณะทำงานผู้ร่วมทบทวนและอนุมัติ", ln=True)
            pdf.set_font("Sarabun", size=9) if os.path.exists(font_path) else pdf.set_font("Arial", size=9)
            pdf.ln(2)

            if len(reviewers) > 0:
                for rev in reviewers:
                    y_curr = pdf.get_y()
                    if y_curr > 250:
                        pdf.add_page()
                        y_curr = pdf.get_y()
                    
                    pdf.cell(90, 5, txt=f"บทบาท: {rev['role']}", ln=0)
                    pdf.cell(90, 5, txt=f"วันที่: {datetime.now().strftime('%Y-%m-%d')}", ln=1)
                    
                    if rev['sig_path'] and os.path.exists(rev['sig_path']):
                        try:
                            pdf.image(rev['sig_path'], x=20, y=pdf.get_y(), h=12)
                        except:
                            pass
                    
                    pdf.cell(90, 14, txt=f"ลงชื่อ: ........................................................", ln=1)
                    pdf.cell(90, 5, txt=f"({rev['name']})", ln=0)
                    pdf.cell(90, 5, txt=f"ตำแหน่ง: {rev['position']}", ln=1)
                    pdf.ln(4)
            else:
                pdf.cell(0, 6, txt="(ไม่ได้เลือกรายชื่อผู้ร่วมทบทวนในรายงานฉบับนี้)", ln=True)

            tmp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            pdf.output(tmp_pdf.name)
            return tmp_pdf.name

        if st.button("💾 บันทึกและออกเอกสารคุณภาพ (PDF) พร้อมรายชื่อคณะทำงานที่เลือก"):
            try:
                plt.figure(figsize=(8, 3.5), dpi=300)
                plt.plot(list(thai_budget_months.values()), merged_trend['Count'], marker='o', color='#1f77b4', linewidth=2, markersize=6)
                plt.title(f"Trend Analysis: {selected_risk_item}", fontsize=11)
                plt.xlabel("Month (Fiscal Year)", fontsize=9)
                plt.ylabel("Incidents Count", fontsize=9)
                plt.grid(True, linestyle='--', alpha=0.6)
                plt.tight_layout()
                
                tmp_img = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                plt.savefig(tmp_img.name, format='png', dpi=300)
                plt.close()
                fig_img_path = tmp_img.name

                report_data = {
                    'risk_name': selected_risk_item,
                    'risk_lvl': risk_lvl_val,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'man': fish_man,
                    'machine': fish_machine,
                    'material': fish_material,
                    'method': fish_method,
                    'env': fish_env,
                    'corr_act': corrective_action,
                    'prev_act': preventive_action,
                    'reviewers': selected_reviewers_for_report,
                    'fig_path': fig_img_path
                }
                st.session_state['saved_capa_reports'].append(report_data)

                pdf_file_path = generate_capa_pdf_with_master_list(
                    selected_risk_item, risk_lvl_val, 
                    fish_man, fish_machine, fish_material, fish_method, fish_env,
                    corrective_action, preventive_action, selected_reviewers_for_report, fig_img_path
                )
                
                with open(pdf_file_path, "rb") as f:
                    st.download_button(
                        label="📥 คลิกดาวน์โหลดเอกสาร PDF (รพ.นาโพธิ์)",
                        data=f,
                        file_name=f"CAPA_Report_NaPho_{selected_risk_item[:15]}.pdf",
                        mime="application/pdf"
                    )
                st.success("สร้างรายงาน PDF สำเร็จ! ระบบดึงรายชื่อคณะทำงานมาลงนามให้อัตโนมัติเรียบร้อยครับ")
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาดในการสร้าง PDF: {e}")
else:
    st.info("โปรดตรวจสอบข้อมูลในระบบ หรือเลือกเงื่อนไขตัวกรองใหม่อีกครั้ง")