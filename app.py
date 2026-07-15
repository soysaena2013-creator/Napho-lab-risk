# --- วางโค้ดชุดนี้แทนที่ส่วนการแสดงผลเดิมทั้งหมด ---

# 0. ชื่อแดชบอร์ด
st.title("🏥 Dashboard ติดตามความเสี่ยงห้องปฏิบัติการ")

# 1. การคำนวณข้อมูลสำหรับแผนภูมิแท่ง (สรุปตามหน่วยงาน)
# จัดกลุ่มตามหน่วยงานและนับจำนวนความเสี่ยง
unit_summary = df_filtered.groupby('4.หน่วยงานที่ทำให้เกิดความเสี่ยง').size().reset_index(name='count')

# 2. แผนภูมิแท่งสรุปแยกตามหน่วยงาน
st.subheader("จำนวนความเสี่ยงแยกตามหน่วยงาน")
fig_bar = px.bar(unit_summary, x='4.หน่วยงานที่ทำให้เกิดความเสี่ยง', y='count')
st.plotly_chart(fig_bar, use_container_width=True)

# 3. การคำนวณข้อมูลสำหรับตารางสรุปและ Risk Matrix (รวมทุกหน่วยงาน)
sev_col_name = [c for c in df.columns if 'ระดับความรุนแรงทางคลินิก' in c][0] 
risk_cols = [c for c in df.columns if 'ระบุความเสี่ยงย่อย' in c]

df_melted = df_filtered.melt(id_vars=[sev_col_name], value_vars=risk_cols, value_name='Risk_Detail')
df_melted = df_melted[df_melted['Risk_Detail'].notna() & (df_melted['Risk_Detail'] != '')]

risk_summary = df_melted.groupby(['Risk_Detail']).agg(
    Frequency=('Risk_Detail', 'count'),
    Severity_Raw=(sev_col_name, lambda x: x.iloc[0])
).reset_index()

risk_summary['Freq_Score'] = risk_summary['Frequency'].apply(get_freq_score)
risk_summary['Sev_Score'] = risk_summary['Severity_Raw'].apply(get_severity_score)
risk_summary['Risk_Matrix'] = risk_summary['Freq_Score'] * risk_summary['Sev_Score']
risk_summary = risk_summary.sort_values(by='Risk_Matrix', ascending=False)

# 4. แสดงผลตารางสรุป (อยู่บน)
st.markdown("---")
st.subheader("ตารางสรุป Risk Matrix (รวมทุกหน่วยงาน)")
st.dataframe(risk_summary[['Risk_Detail', 'Frequency', 'Freq_Score', 'Sev_Score', 'Risk_Matrix']], 
             use_container_width=True, hide_index=True, height=200)

# 5. แสดงผลแผนภูมิ Risk Matrix (อยู่ล่าง)
st.subheader("Risk Matrix Visualization")
fig_matrix = px.scatter(risk_summary, x="Freq_Score", y="Sev_Score", size="Frequency", 
                        color="Risk_Matrix", hover_name="Risk_Detail",
                        range_x=[0.5, 4.5], range_y=[0.5, 4.5])
st.plotly_chart(fig_matrix, use_container_width=True)

# --- จบการวางโค้ด ---