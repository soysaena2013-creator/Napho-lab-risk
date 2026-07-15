import streamlit as st
import pandas as pd
import plotly.express as px

# ฟังก์ชันคำนวณคะแนน
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

def get_risk_level(score):
    if score >= 7: return 'สูงมาก (สีแดง)'
    elif score >= 5: return 'สูง (สีส้ม)'
    elif score >= 4: return 'ปานกลาง (สีเหลือง)'
    else: return 'ต่ำ (สีเขียว)'

st.set_page_config(layout="wide")

# โหลดข้อมูล
@st.cache_data
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS8i7qAIxzDWkWCEnZZEjn8xLY8PT7edgUuTtEsh6aMjBHbj2qo-By5X7LxB1VjMovP9U-FUOkupWUm/pub?output=csv" 
    df = pd.read_csv(url)
    df['Date'] = pd.to_datetime(df['1.วันที่เกิดความเสี่ยง'], dayfirst=True)
    return df

df = load_data()

# Sidebar
year = st.sidebar.multiselect("เลือกปี", df['Date'].dt.year.unique())
df_f = df.copy()
if year: df_f = df_f[df_f['Date'].dt.year.isin(year)]

st.title("🏥 Dashboard ติดตามความเสี่ยง")

# คำนวณ Risk Matrix
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
    matrix_df = matrix_df.sort_values('Risk_Matrix', ascending=False)

    # ตาราง
    color_emoji = {'สูงมาก (สีแดง)': '🔴 สูงมาก', 'สูง (สีส้ม)': '🟠 สูง', 'ปานกลาง (สีเหลือง)': '🟡 ปานกลาง', 'ต่ำ (สีเขียว)': '🟢 ต่ำ'}
    display_df = matrix_df[['Risk_Detail', 'Frequency', 'Risk_Matrix', 'Risk_Level']].copy()
    display_df['ระดับความเสี่ยง'] = display_df['Risk_Level'].map(color_emoji)
    
    st.subheader("ตาราง Risk Matrix")
    st.dataframe(display_df[['Risk_Detail', 'Frequency', 'Risk_Matrix', 'ระดับความเสี่ยง']], use_container_width=True, hide_index=True)

    # แผนภูมิ
    st.subheader("แผนภูมิ Risk Matrix")
    fig = px.scatter(matrix_df, x='Freq_Score', y='Sev_Score', size='Frequency', color='Risk_Matrix',
                     color_continuous_scale=[[0.0, "#008000"], [0.3, "#FFFF00"], [0.6, "#FFA500"], [1.0, "#FF0000"]],
                     text='Risk_Detail', range_x=[0.5, 4.5], range_y=[0.5, 4.5])
    fig.update_traces(textposition='top center', textfont=dict(size=10))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.write("ไม่พบข้อมูล")