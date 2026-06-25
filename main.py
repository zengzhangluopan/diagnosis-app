#!/usr/bin/env python3
"""
观复·电商诊断 - 密码保护入口
Streamlit Cloud启动文件，验证通过后import app模块
密码在 Streamlit Cloud → Settings → Secrets 中配置: app_password = "你的密码"
默认密码: guanfu2026
"""
import streamlit as st
import os
import sys

# ===== 密码保护 =====
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
# ===== 密码保护结束 =====

# 设置项目路径
APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)
sys.path.insert(0, os.path.join(APP_DIR, 'scripts'))

# 验证通过后直接import app，app.py的所有streamlit代码会在当前上下文中执行
import app
