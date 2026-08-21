import streamlit as st
import os, sys, tempfile

st.set_page_config(page_title="测试", layout="wide")

st.title("📊 文件上传测试")
st.write("如果你能看到这个页面，说明基础功能正常")

f = st.file_uploader("上传一个CSV文件测试", type=["csv", "xls", "xlsx"])

if f is not None:
    st.success(f"文件上传成功: {f.name} ({f.size} bytes)")
    st.write(f"文件类型: {f.type}")
    
    # Try saving to temp
    try:
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, f.name)
        with open(temp_path, "wb") as out:
            out.write(f.getbuffer())
        st.success(f"文件保存成功: {temp_path}")
        st.write(f"文件存在: {os.path.exists(temp_path)}")
    except Exception as e:
        st.error(f"保存失败: {e}")
else:
    st.info("请上传一个文件")
