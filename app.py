import streamlit as st
import pandas as pd
import plotly.express as px

# 1. ตั้งค่าหน้าเว็บ
st.set_page_config(layout="wide")

# 2. โหลดข้อมูล (เปลี่ยนลิงก์เป็นลิงก์ CSV ของคุณ)
@st.cache_data
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS8i7qAIxzDWkWCEnZZEjn8xLY8PT7edgUuTtEsh6aMjBHbj2qo-By5X7LxB1VjMovP9U-FUOkupWUm/pub?output=csv" 
    df = pd.read_csv(url) 
    df['Date'] = pd.to_datetime(df['1.วันที่เกิดความเสี่ยง'], dayfirst=True)
    return df

df = load_data()

# 3. ชื่อ Dashboard
st.title("🏥 Dashboard ติดตามความเสี่ยงทางห้องปฏิบัติการ")

# 4. แผนภูมิแท่งสีน้ำเงิน (สรุปแยกตามหน่วยงาน)
st.subheader("จำนวนความเสี่ยงแยกตามหน่วยงาน")
unit_summary = df.groupby('4.หน่วยงานที่ทำให้เกิดความเสี่ยง').size().reset_index(name='count')

fig_bar = px.bar(
    unit_summary, 
    x='4.หน่วยงานที่ทำให้เกิดความเสี่ยง', 
    y='count',
    color_discrete_sequence=['#1f77b4'] # สีน้ำเงิน
)
st.plotly_chart(fig_bar, use_container_width=True)

# 5. ใส่ส่วนตารางและ Risk Matrix ต่อจากนี้ได้เลยครับ