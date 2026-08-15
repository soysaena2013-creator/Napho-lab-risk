import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

# --- 1. ฟังก์ชันสนับสนุนการคำนวณ Risk Matrix ---
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

# --- 2. การตั้งค่าหน้าเว็บ ---
st.set_page_config(layout="wide")
st.title("🏥 Dashboard ติดตามความเสี่ยงทางห้องปฏิบัติการ")

# --- 3. โหลดข้อมูล ---
@st.cache_data
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS8i7qAIxzDWkWCEnZZEjn8xLY8PT7edgUuTtEsh6aMjBHbj2qo-By5X7LxB1VjMovP9U-FUOkupWUm/pub?output=csv" 
    df = pd.read_csv(url)
    df['Date'] = pd.to_datetime(df['1.วันที่เกิดความเสี่ยง'], dayfirst=True, errors='coerce')
    return df

try:
    df = load_data()

    # --- 4. Sidebar Filters ---
    st.sidebar.header("เครื่องมือสืบค้น")
    year = st.sidebar.multiselect("เลือกปี", sorted(df['Date'].dt.year.dropna().unique()))
    quarter = st.sidebar.multiselect("เลือกไตรมาส", [1, 2, 3, 4])

    month_names = {
        1: "มกราคม", 2: "กุมภาพันธ์", 3: "มีนาคม", 4: "เมษายน",
        5: "พฤษภาคม", 6: "มิถุนายน", 7: "กรกฎาคม", 8: "สิงหาคม",
        9: "กันยายน", 10: "ตุลาคม", 11: "พฤศจิกายน", 12: "ธันวาคม"
    }
    available_months = sorted(df['Date'].dt.month.dropna().unique())
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

    # --- 5. แสดงผล Dashboard ---
    matched_cols = [c for c in df_f.columns if 'รูปแบบเหตุการณ์' in str(c)]
    
    st.subheader("จำนวนความเสี่ยงแยกตามหน่วยงานและรูปแบบเหตุการณ์")
    if matched_cols and not df_f.empty:
        col_name = matched_cols[0]
        bar_df = df_f.groupby(['4.หน่วยงานที่ทำให้เกิดความเสี่ยง', col_name]).size().reset_index(name='count')
        fig_bar = px.bar(bar_df, x='4.หน่วยงานที่ทำให้เกิดความเสี่ยง', y='count', color=col_name, barmode='group', text_auto=True)
        st.plotly_chart(fig_bar, use_container_width=True)
    
    st.subheader("ตารางสรุปสถิติอุบัติการณ์")
    if matched_cols and not df_f.empty:
        stats_df = df_f.groupby(['4.หน่วยงานที่ทำให้เกิดความเสี่ยง', col_name]).size().unstack(fill_value=0)
        stats_df['รวม'] = stats_df.sum(axis=1)
        st.dataframe(stats_df, use_container_width=True)

    # --- 6. Risk Matrix ---
    st.subheader("ตาราง Risk Matrix (สรุปรายความเสี่ยงย่อย)")
    risk_cols = [c for c in df.columns if 'ระบุความเสี่ยงย่อย' in c]
    sev_col = [c for c in df.columns if 'ระดับความรุนแรงทางคลินิก' in c]
    
    if risk_cols and sev_col and not df_f.empty:
        melted = df_f.melt(value_vars=risk_cols, value_name='Risk_Detail').dropna(subset=['Risk_Detail'])
        melted = melted[melted['Risk_Detail'] != '']
        
        if not melted.empty:
            matrix_df = melted.groupby('Risk_Detail').size().reset_index(name='Frequency')
            
            def find_max_sev(risk):
                rows = df_f[df_f.apply(lambda row: risk in row.values, axis=1)]
                return rows[sev_col[0]].iloc[0] if not rows.empty else 'A'

            matrix_df['Sev_Raw'] = matrix_df['Risk_Detail'].apply(find_max_sev)
            matrix_df['Freq_Score'] = matrix_df['Frequency'].apply(get_freq_score)
            matrix_df['Sev_Score'] = matrix_df['Sev_Raw'].apply(get_sev_score)
            matrix_df['Risk_Matrix'] = matrix_df['Freq_Score'] * matrix_df['Sev_Score']
            matrix_df['Risk_Level'] = matrix_df['Risk_Matrix'].apply(get_risk_level)
            
            st.dataframe(matrix_df.sort_values(by='Risk_Matrix', ascending=False), use_container_width=True)
    else:
        st.info("ไม่พบข้อมูลความเสี่ยงในช่วงที่เลือก")

except Exception as e:
    st.error(f"เกิดข้อผิดพลาดในการโหลดข้อมูล: {e}")