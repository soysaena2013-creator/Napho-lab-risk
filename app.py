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
@st.cache_data
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS8i7qAIxzDWkWCEnZZEjn8xLY8PT7edgUuTtEsh6aMjBHbj2qo-By5X7LxB1VjMovP9U-FUOkupWUm/pub?output=csv" 
    df = pd.read_csv(url)
    df['Date'] = pd.to_datetime(df['1.วันที่เกิดความเสี่ยง'], dayfirst=True)
    return df

df = load_data()

# 2. Sidebar Filters (ตัวกรองเดิมของคุณครบถ้วน)
st.sidebar.header("เครื่องมือสืบค้น")
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

# กรองข้อมูลตามเงื่อนไข
df_f = df.copy()
if year: df_f = df_f[df_f['Date'].dt.year.isin(year)]
if quarter: df_f = df_f[df_f['Date'].dt.quarter.isin(quarter)]
if selected_months: df_f = df_f[df_f['Date'].dt.month.isin(selected_months)]
if risk_type: df_f = df_f[df_f['5.ประเภทความเสี่ยง'].isin(risk_type)]
if unit: df_f = df_f[df_f['4.หน่วยงานที่ทำให้เกิดความเสี่ยง'].isin(unit)]

st.title("🏥 Dashboard ติดตามความเสี่ยงทางห้องปฏิบัติการ")

# --- ฟังก์ชันสร้างรายงาน PDF รูปแบบตาราง (เพิ่มคอลัมน์ S ถึง X) ---
class PDFTableReport(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_font("Sarabun", size=9)
            self.cell(0, 5, txt="Hospital Risk Incident Analysis Report (รายงานสรุปความเสี่ยงรายหน่วยงาน - ต่อ)", ln=True, align='L')
            self.ln(2)

def generate_pdf_table(dataframe):
    pdf = PDFTableReport(orientation='L', unit='mm', format='A4') # ใช้ A4 แนวนอน
    pdf.add_page()
    
    # ดึงฟอนต์ Sarabun รองรับภาษาไทย
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
        pdf.set_font("Sarabun", size=14)
    else:
        pdf.set_font("Arial", size=12)

    # หัวข้อรายงาน
    pdf.cell(0, 10, txt="Hospital Risk Incident Analysis Report (รายงานสรุปความเสี่ยงรายหน่วยงานและรายละเอียด S-X)", ln=True, align='C')
    pdf.ln(2)
    
    pdf.set_font("Sarabun", size=11) if os.path.exists(font_path) else pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, txt=f"Total Filtered Incidents: {len(dataframe)} cases", ln=True, align='L')
    pdf.ln(4)

    # กำหนดหัวข้อคอลัมน์และความกว้าง (รวม ~277 มม. พอดีหน้ากระดาษ A4 แนวนอน)
    # คอลัมน์ประกอบด้วย: ลำดับ | วันที่ | หน่วยงาน | ช่วงเวร | ปัญหาที่พบ (S) | LEVEL (T) | สาเหตุเกิดจาก (U) | การแก้ไขเบื้องต้น (V) | ผลการแก้ไข (W) | ผลกระทบต่อคนไข้ (X)
    col_widths = [12, 22, 25, 20, 38, 15, 38, 35, 36, 36]
    headers = ["ลำดับ", "วันที่", "หน่วยงาน", "ช่วงเวร", "ปัญหาที่พบ", "LEVEL", "สาเหตุเกิดจาก", "การแก้ไขเบื้องต้น", "ผลการแก้ไข", "ผลกระทบต่อคนไข้"]

    # พิมพ์ Header ของตาราง
    pdf.set_font("Sarabun", size=9)
    pdf.set_fill_color(220, 230, 242) # สีพื้นหลังหัวตาราง
    
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 8, txt=h, border=1, align='C', fill=True)
    pdf.ln()

    # วนลูปข้อมูลใส่ตาราง
    pdf.set_font("Sarabun", size=8)
    for idx, row in dataframe.iterrows():
        date_str = str(row['Date'].strftime('%Y-%m-%d')) if pd.notnull(row['Date']) else '-'
        unit_name = str(row.get('4.หน่วยงานที่ทำให้เกิดความเสี่ยง', '-'))
        shift_val = str(row.get('3.ช่วงเวรที่เกิดความเสี่ยง', '-'))
        
        # ดึงข้อมูลจากคอลัมน์ S ถึง X ตามชื่อฟิลด์จริง
        prob_val = str(row.get('ปัญหาที่พบ', '-'))
        level_val = str(row.get('LEVEL', '-'))
        cause_val = str(row.get('สาเหตุเกิดจาก', '-'))
        solve_val = str(row.get('การแก้ไขปัญหาเบื้องต้น', '-'))
        result_val = str(row.get('ผลการแก้ไข', '-'))
        impact_val = str(row.get('ผลกระทบต่อคนไข้', '-'))

        # ตรวจสอบความสูงหน้ากระดาษ เพื่อขึ้นหน้าใหม่หากหน้าเต็ม
        if pdf.get_y() > 185:
            pdf.add_page()
            pdf.set_font("Sarabun", size=9)
            for i, h in enumerate(headers):
                pdf.cell(col_widths[i], 8, txt=h, border=1, align='C', fill=True)
            pdf.ln()
            pdf.set_font("Sarabun", size=8)

        # พิมพ์แถวข้อมูลลงตาราง (ตัดข้อความให้พอดีเซลล์)
        pdf.cell(col_widths[0], 6, txt=str(idx+1), border=1, align='C')
        pdf.cell(col_widths[1], 6, txt=date_str, border=1, align='C')
        pdf.cell(col_widths[2], 6, txt=unit_name[:15], border=1, align='L')
        pdf.cell(col_widths[3], 6, txt=shift_val[:12], border=1, align='C')
        pdf.cell(col_widths[4], 6, txt=prob_val[:22], border=1, align='L')
        pdf.cell(col_widths[5], 6, txt=level_val[:8], border=1, align='C')
        pdf.cell(col_widths[6], 6, txt=cause_val[:22], border=1, align='L')
        pdf.cell(col_widths[7], 6, txt=solve_val[:20], border=1, align='L')
        pdf.cell(col_widths[8], 6, txt=result_val[:20], border=1, align='L')
        pdf.cell(col_widths[9], 6, txt=impact_val[:20], border=1, align='L')
        pdf.ln()

    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf.output(tmp_file.name)
    return tmp_file.name

st.sidebar.markdown("---")
st.sidebar.subheader("ออกรายงาน")
if st.sidebar.button("📥 ดาวน์โหลดรายงาน PDF (ตาราง + รายละเอียด S-X)"):
    try:
        pdf_path = generate_pdf_table(df_f)
        with open(pdf_path, "rb") as f:
            st.sidebar.download_button(
                label="คลิกเพื่อบันทึกไฟล์ PDF",
                data=f,
                file_name="Risk_Analysis_Report_SX.pdf",
                mime="application/pdf"
            )
    except Exception as e:
        st.sidebar.error(f"สร้าง PDF ไม่สำเร็จ: {e}")

# --- 1. แผนภูมิแท่งแยกตามหน่วยงานและรูปแบบเหตุการณ์ (Miss vs Near Miss) ---
st.subheader("จำนวนความเสี่ยงแยกตามหน่วยงานและรูปแบบเหตุการณ์")

matched_cols = [c for c in df_f.columns if 'รูปแบบเหตุการณ์' in str(c)]

if matched_cols and not df_f.empty:
    col_name = matched_cols[0]
    bar_df = df_f.groupby(['4.หน่วยงานที่ทำให้เกิดความเสี่ยง', col_name]).size().reset_index(name='count')
    
    fig_bar = px.bar(
        bar_df, 
        x='4.หน่วยงานที่ทำให้เกิดความเสี่ยง', 
        y='count', 
        color=col_name, 
        barmode='group', 
        text_auto=True
    )
    st.plotly_chart(fig_bar, use_container_width=True)
else:
    unit_sum = df_f.groupby('4.หน่วยงานที่ทำให้เกิดความเสี่ยง').size().reset_index(name='count')
    st.plotly_chart(px.bar(unit_sum, x='4.หน่วยงานที่ทำให้เกิดความเสี่ยง', y='count', color_discrete_sequence=['#1f77b4'], text_auto=True), use_container_width=True)

# --- 2. ตารางสรุปสถิติอุบัติการณ์ (Miss vs Near Miss) ---
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
    st.info("ไม่พบข้อมูลคอลัมน์ที่มีคำว่า 'รูปแบบเหตุการณ์' ในไฟล์ หรือไม่มีข้อมูลในช่วงที่เลือก")

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
    
    st.dataframe(
        display_df[['Risk_Detail', 'Frequency', 'Freq_Score', 'Sev_Score', 'Risk_Matrix', 'ระดับความเสี่ยง']], 
        use_container_width=True, 
        hide_index=True
    )
    
    st.subheader("แผนภูมิ Risk Matrix (แสดงชื่อความเสี่ยงย่อย)")
    matrix_df['x_jitter'] = matrix_df['Freq_Score'] + np.random.uniform(-0.05, 0.05, size=len(matrix_df))
    matrix_df['y_jitter'] = matrix_df['Sev_Score'] + np.random.uniform(-0.05, 0.05, size=len(matrix_df))

    fig = px.scatter(
        matrix_df, 
        x='x_jitter', 
        y='y_jitter', 
        size='Frequency', 
        color='Risk_Matrix',
        color_continuous_scale=[[0.0, "#008000"], [0.3, "#FFFF00"], [0.6, "#FFA500"], [1.0, "#FF0000"]],
        hover_name='Risk_Detail', 
        range_x=[0.5, 4.5], 
        range_y=[0.5, 4.5]
    )
    st.plotly_chart(fig, use_container_width=True)

else:
    st.write("ไม่พบข้อมูลความเสี่ยงในช่วงที่เลือก")