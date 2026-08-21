import streamlit as st
import os

st.set_page_config(page_title="测试2", layout="wide")
st.title("🔍 超简上传测试")
st.info("这个版本不限制文件类型，也不读取文件内容")

# 不限制文件类型
f = st.file_uploader("上传任意文件")

if f is not None:
    st.success(f"✅ 文件已选择: {f.name}")
    st.write(f"文件大小: {f.size} bytes")
    st.write(f"文件类型: {f.type}")
    st.balloons()
else:
    st.warning("请选择一个文件")
