# --- ฟังก์ชันสร้างรายงาน PDF (ปรับปรุงหัวตารางให้ตัดบรรทัดสวยงาม ไม่ทับซ้อน) ---
class PDFTableReport(FPDF):
    def header(self):
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
        "การแก้ไขปัญหาเฉพาะหน้า",  
        "การแก้ไขเบื้องต้น", 
        "ผลการแก้ไข (W)", 
        "ผลกระทบต่อคนไข้ (X)"
    ]
    
    col_widths = [9, 20, 22, 14, 28, 25, 11, 26, 28, 26, 28, 38] 

    # --- วาดหัวตารางแบบรองรับ Multi-line ป้องกันตัวหนังสือทับกัน ---
    pdf.set_font("Sarabun", size=7) if os.path.exists(font_path) else pdf.set_font("Arial", size=7)
    pdf.set_fill_color(41, 128, 185)
    pdf.set_text_color(255, 255, 255)
    
    header_height = 10  # ขยายความสูงหัวตารางรองรับ 2 บรรทัด
    x_start_hdr = pdf.get_x()
    y_start_hdr = pdf.get_y()
    
    max_h_line = 3.2
    for i, h in enumerate(headers):
        x_curr = pdf.get_x()
        y_curr = pdf.get_y()
        # วาดกรอบพื้นหลังก่อน
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

        # คำนวณความสูงแถวตามจำนวนบรรทัด
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

        # ตรวจสอบพื้นที่หน้ากระดาษ
        if pdf.get_y() + row_height > 195:
            pdf.add_page()
            # พิมพ์หัวตารางซ้ำในหน้าใหม่
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