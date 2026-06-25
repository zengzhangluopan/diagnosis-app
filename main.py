#!/usr/bin/env python3
"""
观复·电商诊断 - 密码保护入口
Streamlit Cloud部署时把启动文件设为 main.py
密码在 Streamlit Cloud → Settings → Secrets 中配置: app_password = "你的密码"
默认密码: guanfu2026
"""
import streamlit as st
import os

def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets.get("app_password", "guanfu2026"):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("## 🔐 观复·电商诊断")
        st.text_input("请输入访问密码", type="password", on_change=password_entered, key="password")
        st.caption("首次访问请联系管理员获取密码")
        return False
    if not st.session_state["password_correct"]:
        st.markdown("## 🔐 观复·电商诊断")
        st.text_input("密码错误，请重新输入", type="password", on_change=password_entered, key="password")
        st.error("密码不正确")
        return False
    return True

if not check_password():
    st.stop()

# 验证通过，执行主应用
app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
with open(app_path, "r", encoding="utf-8") as f:
    exec(f.read(), {"__name__": "__main__", "__file__": app_path})
