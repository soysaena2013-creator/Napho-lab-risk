import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import io
import requests
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from fpdf import FPDF
import tempfile
import os
from datetime import datetime
from PIL import Image as PILImage

# --- ตั้งค่าฟอนต์ภาษาไทยสำหรับ Matplotlib ---
def setup_matplotlib_font():
    font_path = "Sarabun-Regular.ttf"
    if not os.path.exists(font_path) or os.path.getsize(font_path) < 1000:
        try:
            r = requests.get("https://github.com/google/fonts/raw/main/ofl/sarabun/Sarabun-Regular.ttf", timeout=5)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(font_path, "wb") as f:
                    f.write(r.content)
        except:
            pass
    if os.path.exists(font_path):
        fm.fontManager.addfont(font_path)
        plt.rcParams['font.family'] = 'Sarabun'

setup_matplotlib_font()

# --- ฟังก์ชันสนับสนุนและการประเมินความเสี่ยง (Metrics & Risk Matrix) ---
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

# --- ฟังก์ชันจัดการฟอนต์ภาษาไทยสำหรับ fpdf2 ---
def setup_pdf_font(pdf):
    font_path = "Sarabun-Regular.ttf"
    font_bold_path = "Sarabun-Bold.ttf"
    
    for path, url in [(font_path, "https://github.com/google/fonts/raw/main/ofl/sarabun/Sarabun-Regular.ttf"),
                      (font_bold_path, "https://github.com/google/fonts/raw/main/ofl/sarabun/Sarabun-Bold.ttf")]:
        if not os.path.exists(path) or os.path.getsize(path) < 1000:
            try:
                r = requests.get(url, timeout=5)
                if r.status_code == 200 and len(r.content) > 1000:
                    with open(path, "wb") as f:
                        f.write(r.content)
            except:
                pass

    try:
        if os.path.exists(font_path) and os.path.getsize(font_path) > 1000:
            pdf.add_font("Sarabun", "", font_path)
        if os.path.exists(font_bold_path) and os.path.getsize(font_bold_path) > 1000:
            pdf.add_font("Sarabun", "B", font_bold_path)
        else:
            pdf.add_font("Sarabun", "B", font_path)
        return "Sarabun"
    except Exception as e:
        return "Arial"

# ----------------------------------------------------
st.set_page_config(layout="wide")

if 'saved_capa_reports' not in st.session_state:
    st.session_state['saved_capa_reports'] = []

if 'master_reviewers' not in st.session_state:
    st.session_state['master_reviewers'] = [
        {"name": "ทนพ.ศราวุธ สร้อยเสนา", "position": "นักเทคนิคการแพทย์ชำนาญการ", "role": "ผู้ทบทวนความเสี่ยง", "sig_path": None},
        {"name": "ทนพญ.ปรีดา ชาไข", "position": "นักเทคนิคการแพทย์ปฏิบัติการ", "role": "ผู้ร่วมทบทวนความเสี่ยง", "sig_path": None},
        {"name": "ทนพญ.รุ่งนภา สอนจันทร์", "position": "นักเทคนิคการแพทย์", "role": "ผู้ร่วมทบทวนความเสี่ยง", "sig_path": None},
        {"name": "นางสาวลลิดา แก้วบุดศา", "position": "เจ้าพนักงานวิทยาศาสตร์ชำนาญงาน", "role": "ผู้ร่วมทบทวนความเสี่ยง", "sig_path": None},
        {"name": "นางสาวประณีต มิ่งไธสง", "position": "พนักงานวิทยาศาสตร์", "role": "ผู้ร่วมทบทวนความเสี่ยง", "sig_path": None},
        {"name": "ทนพ.ศราวุธ สร้อยเสนา", "position": "นักเทคนิคการแพทย์ชำนาญการ", "role": "ผู้จัดการความเสี่ยง", "sig_path": None},
        {"name": "นพ.เวฬุวัน อินทอง", "position": "ผู้อำนวยการโรงพยาบาลนาโพธิ์", "role": "ผู้อนุมัติ", "sig_path": None},
    ]

if 'capa_pdf_path' not in st.session_state:
    st.session_state['capa_pdf_path'] = None

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

st.sidebar.header("เครื่องมือสืบค้น")
if st.sidebar.button("🔄 โหลดข้อมูลใหม่ทันที"):
    st.cache_data.clear()
    st.session_state['capa_pdf_path'] = None
    st.rerun()

if not df.empty:
    available_budget_years = sorted([int(y) for y in df['Thai_Budget_Year'].dropna().unique()], reverse=True)
    selected_budget_years = st.sidebar.multiselect("เลือกปีงบประมาณ (ไทย)", available_budget_years)
    quarter = st.sidebar.multiselect("เลือกไตรมาส", [1, 2, 3, 4])
    risk_type = st.sidebar.multiselect("ประเภทความเสี่ยง", df['5.ประเภทความเสี่ยง'].dropna().unique())
    unit = st.sidebar.multiselect("หน่วยงาน", df['4.หน่วยงานที่ทำให้เกิดความเสี่ยง'].dropna().unique())

    df_f = df.copy()
    if selected_budget_years: df_f = df_f[df_f['Thai_Budget_Year'].isin(selected_budget_years)]
    if quarter: df_f = df_f[df_f['Date'].dt.quarter.isin(quarter)]
    if risk_type: df_f = df_f[df_f['5.ประเภทความเสี่ยง'].isin(risk_type)]
    if unit: df_f = df_f[df_f['4.หน่วยงานที่ทำให้เกิดความเสี่ยง'].isin(unit)]
else:
    df_f = pd.DataFrame()

def extract_cause_values(row, columns_list):
    cause_text = ""
    for col in columns_list:
        col_str = str(col).strip()
        if 'สาเหตุ' in col_str or col_str.startswith('U.') or ' U ' in col_str or col_str == 'U':
            val = str(row.get(col, ''))
            if val and val != 'nan':
                cause_text = val
                break
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
    solve_val = " / ".join([x for x in [v_text, aa_text] if x and x != 'nan'])
    return solve_val if solve_val else '-'

st.title("🏥 Dashboard ติดตามความเสี่ยงทางห้องปฏิบัติการ (รพ.นาโพธิ์)")

# --- ส่วนแสดง Metrics และ ลูกบอลสีสรุปภาพรวม ---
if not df_f.empty:
    total_risks = len(df_f)
    st.markdown("### 📊 ภาพรวมสถิติความเสี่ยง")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="📌 ความเสี่ยงทั้งหมด", value=f"{total_risks} เรื่อง")
    with col2:
        st.metric(label="🏢 แผนกที่เกิดสูงสุด", value=str(df_f['4.หน่วยงานที่ทำให้เกิดความเสี่ยง'].mode()[0] if not df_f['4.หน่วยงานที่ทำให้เกิดความเสี่ยง'].mode().empty else "-"))
    with col3:
        st.metric(label="⚠️ ประเภทสูงสุด", value=str(df_f['5.ประเภทความเสี่ยง'].mode()[0] if not df_f['5.ประเภทความเสี่ยง'].mode().empty else "-"))
    with col4:
        st.metric(label="📅 ปีงบประมาณ", value=str(selected_budget_years[0] if selected_budget_years else "ทุกปี"))

# --- คลาสสร้างรายงาน PDF พร้อมโลโก้หัวกระดาษและลายน้ำ ---
class CAPAPDF(FPDF):
    def header(self):
        logo_path = "image_627406.png"
        if os.path.exists(logo_path):
            try:
                # วางโลโก้จางๆ เป็นลายน้ำตรงกลางหน้ากระดาษ
                self.image(logo_path, x=45, y=70, w=120, h=120)
            except:
                pass
            try:
                # วางโลโก้โรงพยาบาลไว้ที่มุมซ้ายบน (Header สากล)
                self.image(logo_path, x=15, y=8, w=16)
            except:
                pass

def generate_capa_pdf_with_master_list(risk_name, risk_lvl, man, machine, material, method, env, corr_act, prev_act, reviewers, fig_path=None, fish_path=None, dept_df=None, budget_years=None):
    pdf = CAPAPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()
    
    font_name = setup_pdf_font(pdf)
    
    # ส่วนหัวกระดาษสากล (รองรับโลโก้ซ้าย และข้อมูลควบคุมเอกสารขวา)
    pdf.set_xy(35, 10)
    pdf.set_font(font_name, 'B', 14)
    pdf.cell(120, 6, txt="โรงพยาบาลนาโพธิ์ จังหวัดบุรีรัมย์", ln=0, align='L')
    
    pdf.set_font(font_name, '', 9)
    pdf.set_xy(150, 8)
    pdf.cell(50, 4, txt=f"รหัสเอกสาร: CAPA-LAB-2569", ln=1, align='R')
    pdf.set_xy(150, 13)
    pdf.cell(50, 4, txt=f"วันที่พิมพ์: {datetime.now().strftime('%d/%m/%Y')}", ln=1, align='R')
    
    pdf.set_xy(35, 16)
    pdf.set_font(font_name, '', 10)
    pdf.cell(120, 5, txt="กลุ่มงานเทคนิคการแพทย์ (Na Pho Hospital)", ln=True, align='L')
    
    pdf.ln(4)
    pdf.set_font(font_name, 'B', 12)
    pdf.cell(0, 6, txt="รายงานการทบทวนความเสี่ยงและมาตรการป้องกันแก้ไข (CAPA Report)", ln=True, align='C')
    pdf.ln(2)

    budget_str = ", ".join(map(str, budget_years)) if budget_years else "ทุกปีงบประมาณ"
    pdf.set_font(font_name, '', 9.5)
    pdf.cell(0, 5, txt=f"รายการความเสี่ยง: {str(risk_name)} | ระดับความเสี่ยง: {str(risk_lvl)} | ปีงบประมาณ: {budget_str}", ln=True)
    pdf.ln(2)

    if fig_path and os.path.exists(fig_path):
        pdf.set_font(font_name, 'B', 9.5)
        pdf.cell(0, 5, txt="กราฟเส้นแสดงแนวโน้มเปรียบเทียบรายปีงบประมาณ:", ln=True)
        pdf.image(fig_path, x=25, w=160)
        pdf.ln(2)

    if dept_df is not None and not dept_df.empty:
        pdf.set_font(font_name, 'B', 9.5)
        pdf.cell(0, 5, txt="สรุปจำนวนความเสี่ยงแยกตามแผนก/หน่วยงาน สำหรับรายการนี้:", ln=True)
        pdf.set_font(font_name, 'B', 9)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(110, 5, txt="หน่วยงาน/แผนก", border=1, fill=True)
        pdf.cell(50, 5, txt="จำนวนครั้ง (เรื่อง)", border=1, fill=True, ln=True, align='C')
        
        pdf.set_font(font_name, '', 9)
        for _, d_row in dept_df.iterrows():
            pdf.cell(110, 5, txt=str(d_row['หน่วยงาน/แผนก']), border=1)
            pdf.cell(50, 5, txt=str(d_row['จำนวนครั้ง (เรื่อง)']), border=1, ln=True, align='C')
        pdf.ln(3)

    pdf.set_font(font_name, 'B', 10.5)
    pdf.set_fill_color(230, 240, 250)
    pdf.cell(0, 7, txt="  1. การวิเคราะห์สาเหตุ (Root Cause Analysis - ก้างปลา 5M1E)", ln=True, fill=True)
    pdf.ln(2)

    if fish_path and os.path.exists(fish_path):
        pdf.image(fish_path, x=15, w=180)
        pdf.ln(2)

    pdf.set_font(font_name, '', 9)
    pdf.multi_cell(0, 4.5, txt=f"- บุคลากร (Man): {str(man)}\n- เครื่องมือ (Machine): {str(machine)}\n- วัสดุ/สารเคมี (Material): {str(material)}\n- กระบวนการ (Method): {str(method)}\n- สิ่งแวดล้อม (Environment): {str(env)}")
    pdf.ln(2)

    pdf.set_font(font_name, 'B', 10.5)
    pdf.set_fill_color(230, 240, 250)
    pdf.cell(0, 7, txt="  2. แนวทางแก้ไขและป้องกัน (CAPA)", ln=True, fill=True)
    
    pdf.set_font(font_name, '', 9.5)
    pdf.multi_cell(0, 5, txt=f"- มาตรการแก้ไขเฉพาะหน้า: {str(corr_act)}\n- มาตรการป้องกันระยะยาว: {str(prev_act)}")
    pdf.ln(4)

    # ลงนามคณะทำงาน
    block_height_per_row = 45
    estimated_signatures_height = ((len(reviewers) + 1) // 2) * block_height_per_row + 20
    if pdf.get_y() + estimated_signatures_height > 275:
        pdf.add_page()

    pdf.set_font(font_name, 'B', 10.5)
    pdf.cell(0, 6, txt="3. ลงนามคณะทำงานผู้ร่วมทบทวนและอนุมัติ", ln=True)
    pdf.ln(4)

    if len(reviewers) > 0:
        normal_reviewers = [r for r in reviewers if "ผู้อำนวยการ" not in str(r['position']) and "ผู้อนุมัติ" not in str(r['role'])]
        director_reviewers = [r for r in reviewers if "ผู้อำนวยการ" in str(r['position']) or "ผู้อนุมัติ" in str(r['role'])]

        def draw_centered_signature_block(rev, x_pos, y_pos, col_width=90):
            pdf.set_xy(x_pos, y_pos)
            pdf.set_font(font_name, '', 9)
            pdf.cell(col_width, 5, txt=f"บทบาท: {str(rev['role'])}", ln=1, align='C')
            
            sig_y = pdf.get_y()
            is_director = ("ผู้อำนวยการ" in str(rev['position']) or "ผู้อนุมัติ" in str(rev['role']))
            if not is_director and rev['sig_path'] and os.path.exists(rev['sig_path']):
                try:
                    pdf.image(rev['sig_path'], x=x_pos + (col_width - 38) / 2, y=sig_y - 2, w=38, h=19)
                except:
                    pass
            
            pdf.set_xy(x_pos, sig_y + 14)
            pdf.cell(col_width, 5, txt=f"ลงชื่อ: ...........................................", ln=1, align='C')
            pdf.set_x(x_pos)
            pdf.cell(col_width, 5, txt=f"({str(rev['name'])})", ln=1, align='C')
            pdf.set_x(x_pos)
            pdf.cell(col_width, 5, txt=f"ตำแหน่ง: {str(rev['position'])}", ln=1, align='C')
            pdf.set_x(x_pos)
            pdf.cell(col_width, 5, txt=f"วันที่: {datetime.now().strftime('%Y-%m-%d')}", ln=1, align='C')

        i = 0
        while i < len(normal_reviewers):
            if pdf.get_y() + block_height_per_row > 280:
                pdf.add_page()
            y_start = pdf.get_y()
            draw_centered_signature_block(normal_reviewers[i], 15, y_start, col_width=85)
            if i + 1 < len(normal_reviewers):
                draw_centered_signature_block(normal_reviewers[i+1], 110, y_start, col_width=85)
            pdf.set_y(y_start + block_height_per_row)
            i += 2

        for rev in director_reviewers:
            if pdf.get_y() + block_height_per_row > 280:
                pdf.add_page()
            y_start = pdf.get_y() + 2
            draw_centered_signature_block(rev, 60, y_start, col_width=90)
            pdf.set_y(y_start + block_height_per_row)

    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf.output(tmp_file.name)
    return tmp_file.name

# --- ฟอร์มกรอกข้อมูลและเลือกรายการความเสี่ยงใน Streamlit ---
st.markdown("---")
st.subheader("📝 ฟังก์ชันทบทวนความเสี่ยงและออกรายงาน CAPA PDF")
if not df_f.empty:
    risk_cols = [c for c in df.columns if 'ระบุความเสี่ยงย่อย' in c]
    if risk_cols:
        melted_all = df_f.melt(id_vars=[c for c in df_f.columns if c not in risk_cols], value_vars=risk_cols, value_name='Risk_Detail').dropna(subset=['Risk_Detail'])
        unique_risks = sorted(melted_all['Risk_Detail'].unique())
        selected_risk_item = st.selectbox("🎯 เลือกรายการความเสี่ยงที่ต้องการทบทวน:", unique_risks)
        
        # กรองข้อมูลเฉพาะรายการที่เลือกเพื่อดึงแผนกและคำนวณลูกบอลสี
        sub_df = melted_all[melted_all['Risk_Detail'] == selected_risk_item]
        count_item = len(sub_df)
        freq_s = get_freq_score(count_item)
        sev_s = get_sev_score(selected_risk_item)
        risk_score = freq_s * sev_s
        risk_lvl_str = get_risk_level(risk_score)

        # แสดงลูกบอลสีและระดับความเสี่ยงตามเกณฑ์
        color_badge = "🟢 สีเขียว"
        if "แดง" in risk_lvl_str: color_badge = "🔴 สีแดง"
        elif "ส้ม" in risk_lvl_str: color_badge = "🟠 สีส้ม"
        elif "เหลือง" in risk_lvl_str: color_badge = "🟡 สีเหลือง"

        st.info(f"📌 **สรุปการประเมิน:** จำนวนครั้งทั้งหมด **{count_item}** เรื่อง | ระดับความเสี่ยง: **{risk_lvl_str}** ({color_badge})")

        fish_man = st.text_area("👤 บุคลากร (Man):", "เจ้าหน้าที่เวรปฏิบัติงานต่อเนื่องล้าช้า")
        fish_machine = st.text_area("⚙️ เครื่องมือ (Machine):", "ระบบเชื่อมต่อ LIS ขัดข้องชั่วขณะ")
        fish_material = st.text_area("🧪 วัสดุ/สารเคมี (Material):", "คุณภาพสิ่งส่งตรวจหรือน้ำยาควบคุมคุณภาพ")
        fish_method = st.text_area("📋 กระบวนการ (Method):", "ขั้นตอนทบทวนก่อนอนุมัติผล")
        fish_env = st.text_area("🌍 สิ่งแวดล้อม (Environment):", "ความแออัดหน้างาน")
        
        corrective_action = st.text_area("🛠️ มาตรการแก้ไขเฉพาะหน้า:", "ดึงผลตรวจกลับทันที แจ้งแพทย์ผู้รักษา")
        preventive_action = st.text_area("🔒 มาตรการป้องกันระยะยาว:", "กำหนดระบบทบทวนซ้ำและปรับปรุง SOP")

        if st.button("📄 ประมวลผลสร้างรายงาน CAPA PDF รูปแบบสากล"):
            try:
                # สร้างกราฟฟิกจำลองสำหรับใส่ในรายงาน
                fig_dummy, ax = plt.subplots(figsize=(6, 2.5))
                ax.plot([1, 2, 3], [4, 2, 5], marker='o', color='#2980b9')
                ax.set_title("Trend Analysis")
                tmp_fig = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                plt.savefig(tmp_fig.name, bbox_inches='tight', dpi=200)
                plt.close()

                # สร้างแผนภูมิก้างปลาจำลอง
                tmp_fish = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                plt.figure(figsize=(6, 2))
                plt.text(0.5, 0.5, "Fishbone 5M1E Summary Diagram", ha='center', va='center', fontsize=12)
                plt.axis('off')
                plt.savefig(tmp_fish.name, bbox_inches='tight', dpi=200)
                plt.close()

                # สรุปตารางแยกตามแผนกสำหรับรายการนี้
                dept_summary = sub_df.groupby('4.หน่วยงานที่ทำให้เกิดความเสี่ยง').size().reset_index(name='จำนวนครั้ง (เรื่อง)')
                dept_summary.columns = ['หน่วยงาน/แผนก', 'จำนวนครั้ง (เรื่อง)']

                capa_pdf_path = generate_capa_pdf_with_master_list(
                    selected_risk_item, risk_lvl_str, 
                    fish_man, fish_machine, fish_material, fish_method, fish_env, 
                    corrective_action, preventive_action, 
                    st.session_state['master_reviewers'], tmp_fig.name, tmp_fish.name, dept_summary, selected_budget_years
                )
                st.session_state['capa_pdf_path'] = capa_pdf_path
                st.success("สร้างรายงาน CAPA PDF รูปแบบสากลสำเร็จแล้ว!")
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาด: {e}")

        if st.session_state['capa_pdf_path'] and os.path.exists(st.session_state['capa_pdf_path']):
            with open(st.session_state['capa_pdf_path'], "rb") as pdf_file:
                st.download_button(
                    label="📥 คลิกดาวน์โหลดรายงาน CAPA PDF",
                    data=pdf_file,
                    file_name=f"CAPA_Report_Standard.pdf",
                    mime="application/pdf"
                )