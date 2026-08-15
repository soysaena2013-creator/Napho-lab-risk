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

# 1. โหลดข้อมูล (กำหนด ttl=0 และปุ่มเคลียร์แคชเพื่อให้ดึงข้อมูลใหม่ทันที)
@st.cache_data(ttl=0)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS8i7qAIxzDWkWCEnZZEjn8xLY8PT7edgUuTtEsh6aMjBHbj2qo-By5X7LxB1VjMovP9U-FUOkupWUm/pub?output=csv" 
    df = pd.read_csv(url)
    df['Date'] = pd.to_datetime(df['1.วันที่เกิดความเสี่ยง'], dayfirst=True)
    return df

df = load_data()

# 2. Sidebar Filters & Controls
st.sidebar.header("เครื่องมือสืบค้น")

if st.sidebar.button("🔄 โหลดข้อมูลใหม่ทันที"):
    st.cache_data.clear()
    st.rerun()

year = st.sidebar.multiselect("เลือกปี", sorted(df['Date'].dt.year.unique()))
quarter = st.sidebar.multiselect("เลือกไตรมาส", [1, 2, 3, 4])

month_names = {
    1: "มกราคม", 2: "กุมภาพันธ์", 3: "มีนาคม", 4: "เมษายน",
    5: "พฤษภาคม", 6: "มิถุนายน", 7: "กรกฎาคม", 8: "สิงหาคม",
    9: "กันยายน", 10: "ตุลาคม", 11: "พฤศจิกายน", 12: "ธันวาคม"
}
available_months = sorted(df['Date'].dt.month.unique())
month_options = {month_names[m]: m for m in available_months}
selected_month_names = st.sidebar.multiselect("เลือกเดือน", list(month_options.keys()))
selected_months = [month_options[m] for m in selected_month_names]

risk_type = st.sidebar.multiselect("ประเภทความเสี่ยง", df['5.ประเภทความเสี่ยง'].unique())
unit = st.sidebar.multiselect("หน่วยงาน", df['4.หน่วยงานที่ทำให้เกิดความเสี่ยง'].unique())

# กรองข้อมูล
df_f = df.copy()
if year: df_f = df_f[df_f['Date'].dt.year.isin(year)]
if quarter: df_f = df_f[df_f['Date'].dt.quarter.isin(quarter)]
if selected_months: df_f = df_f[df_f['Date'].dt.month.isin(selected_months)]
if risk_type: df_f = df_f[df_f['5.ประเภทความเสี่ยง'].isin(risk_type)]
if unit: df_f = df_f[df_f['4.หน่วยงานที่ทำให้เกิดความเสี่ยง'].isin(unit)]

st.title("🏥 Dashboard ติดตามความเสี่ยงทางห้องปฏิบัติการ")

# --- ฟังก์ชันสร้างรายงาน PDF (จัดสัดส่วนตารางและป้องกันข้อความทับซ้อน) ---
class PDFTableReport(FPDF):
    def header(self):
        # ตั้งค่าหัวกระดาษระยะปลอดภัย
        pass

def generate_pdf_table(dataframe):
    # ใช้ A4 แนวนอน (Landscape: 297 x 210 มม.) ขอบซ้ายขวา 11 มม. เหลือพื้นที่พิมพ์ 275 มม.
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

    # Title รายงาน
    pdf.cell(0, 6, txt="Hospital Risk Incident Analysis Report (รายงานสรุปความเสี่ยงและรายละเอียด)", ln=True, align='C')
    pdf.set_font("Sarabun", size=8) if os.path.exists(font_path) else pdf.set_font("Arial", size=8)
    pdf.cell(0, 5, txt=f"Total Filtered Incidents: {len(dataframe)} cases", ln=True, align='L')
    pdf.ln(2)

    headers = [
        "ลำดับ", 
        "วันที่เกิด", 
        "หน่วยงาน", 
        "ช่วงเวร", 
        "ความเสี่ยงที่เกิด", 
        "ปัญหาที่พบ (S)", 
        "LEVEL (T)", 
        "สาเหตุเกิดจาก (U)", 
        "การแก้ไขปัญหาเฉพาะหน้า",  # คอลัมน์ Z
        "การแก้ไขเบื้องต้น", 
        "ผลการแก้ไข (W)", 
        "ผลกระทบต่อคนไข้ (X)"
    ]
    
    # กำหนดความกว้างคอลัมน์รวมกันพอดี 275 มม. ไม่ให้ล้นและไม่ทับกัน
    col_widths = [9, 20, 22, 14, 28, 25, 11, 26, 28, 26, 28, 38] 

    pdf.set_font("Sarabun", size=8) if os.path.exists(font_path) else pdf.set_font("Arial", size=8)
    pdf.set_fill_color(41, 128, 185)
    pdf.set_text_color(255, 255, 255)
    
    header_height = 8
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], header_height, txt=h, border=1, align='C', fill=True)
    pdf.ln()

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Sarabun", size=7) if os.path.exists(font_path) else pdf.set_font("Arial", size=7)

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

        row_data = [
            str(idx+1),
            date_str,
            unit_name,
            shift_val,
            risk_desc,
            prob_val,
            level_val,
            cause_val,
            immediate_fix_val,  
            solve_val,  
            result_val,
            impact_val
        ]

        # คำนวณความสูงแถวตามจำนวนบรรทัดของข้อความที่ยาวที่สุด เพื่อป้องกันข้อความทับซ้อน
        max_lines = 1
        for i, text in enumerate(row_data):
            w = col_widths[i]
            txt_clean = text if text != 'nan' and pd.notnull(text) else '-'
            chars_per_line = max(int(w / 1.7), 3)
            lines = 0
            for paragraph in str(txt_clean).split('\n'):
                if len(paragraph) == 0:
                    lines += 1
                else:
                    lines += max(1, -(-len(paragraph) // chars_per_line))
            if lines > max_lines:
                max_lines = lines

        row_height = max(6.0, (max_lines * line_height) + 2.5)

        # ตรวจสอบพื้นที่หน้ากระดาษ หากไม่พอให้ขึ้นหน้าใหม่พร้อมพิมพ์หัวตารางซ้ำ
        if pdf.get_y() + row_height > 195:
            pdf.add_page()
            pdf.set_font("Sarabun", size=8) if os.path.exists(font_path) else pdf.set_font("Arial", size=8)
            pdf.set_fill_color(41, 128, 185)
            pdf.set_text_color(255, 255, 255)
            for i, h in enumerate(headers):
                pdf.cell(col_widths[i], header_height, txt=h, border=1, align='C', fill=True)
            pdf.ln()
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
if st.sidebar.button("📥 ดาวน์โหลดรายงาน PDF (ข้อมูลครบถ้วน + จัดเต็มบรรทัด)"):
    try:
        pdf_path = generate_pdf_table(df_f)
        with open(pdf_path, "rb") as f:
            st.sidebar.download_button(
                label="คลิกเพื่อบันทึกไฟล์ PDF",
                data=f,
                file_name="Risk_Full_Report_Complete.pdf",
                mime="application/pdf"
            )
    except Exception as e:
        st.sidebar.error(f"สร้าง PDF ไม่สำเร็จ: {e}")

# --- 1. แผนภูมิแท่งแยกตามหน่วยงานและรูปแบบเหตุการณ์ ---
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

# --- 2. ตารางสรุปสถิติอุบัติการณ์ ---
st.subheader("ตารางสรุปสถิติอุบัติการณ์ (Miss vs Near Miss)")
if matched_cols and not df_f.empty:
    col_name = matched_cols[0]
    stats_df = df_f.groupby(['4.หน่วยงานที่ทำให้เกิดความเสี่ยง', col_name]).size().unstack(fill_value=0)
    stats_df['รวม'] = stats_df.sum(axis=1)
    for col in stats_df.columns:
        if col != 'รวม':
            stats_df[f'% {col}'] = (stats_df[col] / stats_df['รวม'] * 100).round(2)
    st.dataframe(stats_df, use_container_width=True)
else:
    st.info("ไม่พบข้อมูลคอลัมน์ที่มีคำว่า 'รูปแบบเหตุการณ์'")

# --- 3. ส่วนคำนวณ Risk Matrix ---
risk_cols = [c for c in df.columns if 'ระบุความเสี่ยงย่อย' in c]
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

    st.subheader("ตาราง Risk Matrix (สรุปรายความเสี่ยงย่อย)")
    color_emoji = {'สูงมาก (สีแดง)': '🔴 สูงมาก', 'สูง (สีส้ม)': '🟠 สูง', 'ปานกลาง (สีเหลือง)': '🟡 ปานกลาง', 'ต่ำ (สีเขียว)': '🟢 ต่ำ'}
    display_df = matrix_df.copy()
    display_df['ระดับความเสี่ยง'] = display_df['Risk_Level'].map(color_emoji)
    
    st.dataframe(display_df[['Risk_Detail', 'Frequency', 'Freq_Score', 'Sev_Score', 'Risk_Matrix', 'ระดับความเสี่ยง']], use_container_width=True, hide_index=True)
    
    st.subheader("แผนภูมิ Risk Matrix (แสดงชื่อความเสี่ยงย่อย)")
    matrix_df['x_jitter'] = matrix_df['Freq_Score'] + np.random.uniform(-0.05, 0.05, size=len(matrix_df))
    matrix_df['y_jitter'] = matrix_df['Sev_Score'] + np.random.uniform(-0.05, 0.05, size=len(matrix_df))

    fig = px.scatter(
        matrix_df, x='x_jitter', y='y_jitter', size='Frequency', color='Risk_Matrix',
        color_continuous_scale=[[0.0, "#008000"], [0.3, "#FFFF00"], [0.6, "#FFA500"], [1.0, "#FF0000"]],
        hover_name='Risk_Detail', range_x=[0.5, 4.5], range_y=[0.5, 4.5]
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.write("ไม่พบข้อมูลความเสี่ยงในช่วงที่เลือก")