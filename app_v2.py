#!/usr/bin/env python3
"""
电商链接诊断 Web应用 V2.0
基于Streamlit，直接调用诊断引擎，不经过LLM

V2.0更新：
- 报告结构重组：4大模块（流量与转化、产品与体验、推广、数据完整性）
- 术语说明模块
- 18维度评分可视化
- 数据完整性校验

启动方式: streamlit run app.py
"""

import streamlit as st
import json
import os
import sys
import tempfile
import time

# 添加项目路径
APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)
sys.path.insert(0, os.path.join(APP_DIR, 'scripts'))

from parse_csv import parse_files
from run_diagnosis import run_diagnosis


# ============================================================
# 维度定义（与引擎 __init__.py 保持一致）
# ============================================================
DIMENSIONS = [
    {'id': 'traffic_quality',       'name': '流量质量精准度',  'layer': '流量端'},
    {'id': 'position_rank',         'name': '位置排名',        'layer': '流量端'},
    {'id': 'time_node',             'name': '时间节点',        'layer': '流量端'},
    {'id': 'traffic_page_match',    'name': '流量-页面匹配度', 'layer': '转化端'},
    {'id': 'main_image_ctr',        'name': '主图点击率',      'layer': '转化端'},
    {'id': 'detail_page_logic',     'name': '详情页五层逻辑',  'layer': '转化端'},
    {'id': 'review_quality',        'name': '评价质量',        'layer': '转化端'},
    {'id': 'wen_dajia',             'name': '问大家',          'layer': '转化端'},
    {'id': 'customer_service',      'name': '客服询单转化',    'layer': '转化端'},
    {'id': 'market_acceptance',     'name': '市场接受度',      'layer': '产品端'},
    {'id': 'price_positioning',     'name': '价格定位',        'layer': '产品端'},
    {'id': 'sku_coverage',          'name': 'SKU覆盖',         'layer': '产品端'},
]

# 术语表
GLOSSARY = {
    '搜索转化率': '用户通过搜索关键词进入商品页后成交的比例，反映链接本身的真实转化能力',
    '蓄水效率': '广告花钱换来的收藏加购意愿，加购率高=蓄水好，用户在观望等待购买时机',
    '真实ROI': '剥离自然流量归因后的广告投入产出比，比表面ROI更接近广告的真实效果',
    '表面ROI': '报表上直接显示的ROI，包含了自然流量成交被算到广告头上的部分',
    '归因虚高': '阿里妈妈把自然流量成交算到广告的比例，虚高越多，表面ROI越不可信',
    '加购率': '点击广告后加入购物车的比例，高加购率=用户有意向但可能在比价',
    '收藏加购成本': '获得一个收藏或加购需要花多少广告费，越低蓄水越高效',
    '拉新层': '以获取新客户为主要目标的推广计划',
    '收割层': '以触达已收藏/加购/浏览过但未购买用户为主的推广计划',
    '全站推广': '同时覆盖拉新和收割的混合型推广计划，不拆分统计',
    '跳失率': '进入页面后没有任何操作就离开的比例，但广告占比高时跳失率高不代表页面差',
    '广告占比': '付费流量占总流量的比例，超过70%时整体指标会被稀释',
}

# 数据完整性检查规则
REQUIRED_FIELDS = {
    '商品概况': {
        'file_keywords': ['商品概况', '商品效果', '商品-'],
        'required_for': ['转化率', '客单价', '月销'],
        'tip': '生意参谋 → 商品 → 商品概况 → 导出',
    },
    '流量来源': {
        'file_keywords': ['流量', '二级来源'],
        'required_for': ['搜索转化率', '广告占比', '跳失率'],
        'tip': '生意参谋 → 流量 → 商品二级来源 → 导出',
    },
    '推广报表': {
        'file_keywords': ['计划报表', '推广', '阿里妈妈'],
        'required_for': ['真实ROI', '归因虚高', '蓄水效率', '加购率'],
        'tip': '阿里妈妈 → 报表 → 计划报表 → 导出',
    },
}


# ============================================================
# 页面配置
# ============================================================
st.set_page_config(
    page_title="电商链接诊断",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 自定义CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        font-weight: 700;
        color: #1a1a2e;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .one-liner {
        font-size: 1.3rem;
        font-weight: 600;
        color: #1a1a2e;
        padding: 1.2rem 1.5rem;
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 12px;
        margin: 1rem 0;
        line-height: 1.6;
    }
    .action-card {
        padding: 1rem 1.2rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        border-left: 4px solid;
    }
    .action-urgent {
        border-color: #e74c3c;
        background: #fdf2f2;
    }
    .action-important {
        border-color: #f39c12;
        background: #fef9e7;
    }
    .action-suggest {
        border-color: #27ae60;
        background: #f0faf0;
    }
    .action-title {
        font-weight: 600;
        font-size: 1.05rem;
        margin-bottom: 0.3rem;
    }
    .action-why {
        color: #555;
        font-size: 0.9rem;
    }
    .data-card {
        padding: 0.8rem 1rem;
        background: #f8f9fa;
        border-radius: 8px;
        margin: 0.3rem 0;
        font-size: 0.95rem;
    }
    .module-card {
        padding: 1.2rem;
        background: #f8f9fa;
        border-radius: 12px;
        margin: 0.8rem 0;
    }
    .module-title {
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    .score-bar {
        height: 8px;
        border-radius: 4px;
        background: #e0e0e0;
        margin: 0.2rem 0;
    }
    .score-fill {
        height: 8px;
        border-radius: 4px;
    }
    .upload-zone {
        border: 2px dashed #ccc;
        border-radius: 12px;
        padding: 2rem;
        text-align: center;
        margin: 1rem 0;
    }
    .step-badge {
        display: inline-block;
        width: 28px;
        height: 28px;
        line-height: 28px;
        border-radius: 50%;
        background: #005FD3;
        color: white;
        text-align: center;
        font-weight: 600;
        margin-right: 0.5rem;
    }
    .progress-step {
        padding: 0.8rem 0;
        font-size: 1rem;
    }
    .glossary-term {
        font-weight: 600;
        color: #333;
    }
    .glossary-def {
        color: #666;
        font-size: 0.9rem;
    }
    .data-missing {
        padding: 0.5rem 0.8rem;
        background: #fff3cd;
        border-left: 3px solid #f39c12;
        border-radius: 6px;
        margin: 0.3rem 0;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# 会话状态初始化
# ============================================================
if 'diagnosis_result' not in st.session_state:
    st.session_state.diagnosis_result = None
if 'parsed_data' not in st.session_state:
    st.session_state.parsed_data = None
if 'uploaded_files' not in st.session_state:
    st.session_state.uploaded_files = None
if 'need_selection' not in st.session_state:
    st.session_state.need_selection = False
if 'available_products' not in st.session_state:
    st.session_state.available_products = []
if 'uploaded_file_names' not in st.session_state:
    st.session_state.uploaded_file_names = []


# ============================================================
# 辅助函数
# ============================================================
def score_color(score):
    """根据分数返回颜色"""
    if score is None:
        return '#ccc'
    if score >= 7:
        return '#27ae60'
    elif score >= 5:
        return '#f39c12'
    else:
        return '#e74c3c'


def score_label(score):
    """根据分数返回标签"""
    if score is None:
        return '无数据'
    if score >= 8:
        return '优秀'
    elif score >= 6:
        return '良好'
    elif score >= 4:
        return '一般'
    else:
        return '较差'


def check_data_completeness(file_names):
    """检查上传文件的数据完整性"""
    missing = []
    found = []
    all_names = ' '.join(file_names).lower() if file_names else ''
    
    for file_type, rules in REQUIRED_FIELDS.items():
        matched = any(kw.lower() in all_names for kw in rules['file_keywords'])
        if matched:
            found.append(file_type)
        else:
            missing.append({
                'type': file_type,
                'required_for': rules['required_for'],
                'tip': rules['tip'],
            })
    
    return found, missing


def render_score_bar(dim_id, dims):
    """渲染单个维度的评分条"""
    dr = dims.get(dim_id, {})
    score = dr.get('score')
    name = dr.get('name', dim_id)
    
    if score is not None:
        color = score_color(score)
        width = max(score * 10, 5)
        return f"""
        <div style="display:flex;align-items:center;margin:0.3rem 0;">
            <div style="width:120px;font-size:0.9rem;color:#333;">{name}</div>
            <div style="flex:1;">
                <div class="score-bar"><div class="score-fill" style="width:{width}%;background:{color};"></div></div>
            </div>
            <div style="width:50px;text-align:right;font-size:0.9rem;font-weight:600;color:{color};">{score}/10</div>
        </div>
        """
    else:
        return f"""
        <div style="display:flex;align-items:center;margin:0.3rem 0;">
            <div style="width:120px;font-size:0.9rem;color:#999;">{name}</div>
            <div style="flex:1;"><div class="score-bar"><div class="score-fill" style="width:0%;background:#ccc;"></div></div></div>
            <div style="width:50px;text-align:right;font-size:0.9rem;color:#999;">—</div>
        </div>
        """


# ============================================================
# 诊断函数
# ============================================================
def run_full_diagnosis(file_paths, product_prefix=None):
    """运行完整诊断流程"""
    parsed = parse_files(file_paths)
    
    if '_errors' in parsed:
        errors = parsed.pop('_errors')
        if not parsed:
            return {'error': f'文件解析失败: {"; ".join(errors)}'}
    
    available_prefixes = parsed.pop('_available_prefixes', None)
    
    if product_prefix:
        parsed['product_prefix'] = product_prefix
    elif available_prefixes and len(available_prefixes) > 1:
        return {
            'status': 'need_selection',
            'available_products': list(available_prefixes.keys()),
            'parsed_data': parsed
        }
    
    try:
        conclusion = run_diagnosis(parsed)
        return conclusion
    except Exception as e:
        return {'error': f'诊断引擎运行失败: {str(e)}'}


def render_report(result):
    """渲染诊断报告 — V2.0 模块化结构"""
    if not result:
        return
    
    # 错误处理
    if 'error' in result:
        st.error(f"❌ {result['error']}")
        return
    
    dims = result.get('dim_results', {})
    ad_diagnosis = result.get('ad_diagnosis')
    data_card = result.get('data_card', [])
    ad_data_card = result.get('ad_data_card', [])
    
    # ---- 一句话结论 ----
    one_liner = result.get('one_liner') or result.get('ad_one_liner', '')
    if one_liner:
        st.markdown(f'<div class="one-liner">📊 {one_liner}</div>', unsafe_allow_html=True)
    
    # ---- 优先动作（去重） ----
    _raw_actions = (result.get('actions') or []) + (result.get('ad_actions') or [])
    _seen = set()
    all_actions = []
    for a in _raw_actions:
        t = a.get('title', '')
        if t not in _seen:
            _seen.add(t)
            all_actions.append(a)
    
    if all_actions:
        st.markdown("### 🎯 优先动作")
        for action in all_actions:
            priority = action.get('priority', 'suggest')
            title = action.get('title', '')
            what = action.get('what', '')
            why = action.get('why', '')
            expected = action.get('expected', '')
            
            css_class = f"action-{priority}"
            icon = {'urgent': '🔴', 'important': '🟡', 'suggest': '🟢'}.get(priority, '🟢')
            label = {'urgent': '紧急', 'important': '重要', 'suggest': '建议'}.get(priority, '建议')
            
            st.markdown(f"""
            <div class="action-card {css_class}">
                <div class="action-title">{icon} {label}：{title}</div>
                <div class="action-why"><b>做什么：</b>{what}</div>
                <div class="action-why"><b>为什么：</b>{why}</div>
                {"<div class='action-why'><b>预期：</b>" + expected + "</div>" if expected else ""}
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # ============================================================
    # 模块一：流量与转化诊断
    # ============================================================
    st.markdown("### 🔄 流量与转化诊断")
    
    # 流量端维度评分
    traffic_dims = [d for d in DIMENSIONS if d['layer'] == '流量端']
    conv_dims = [d for d in DIMENSIONS if d['layer'] == '转化端']
    
    col_traffic, col_conv = st.columns(2)
    
    with col_traffic:
        st.markdown("**流量端**")
        html = ''
        for d in traffic_dims:
            html += render_score_bar(d['id'], dims)
        st.markdown(html, unsafe_allow_html=True)
    
    with col_conv:
        st.markdown("**转化端**")
        html = ''
        for d in conv_dims:
            html += render_score_bar(d['id'], dims)
        st.markdown(html, unsafe_allow_html=True)
    
    # 流量与转化关键指标
    if data_card:
        st.markdown("##### 关键指标")
        # 拆分链接质量指标和生意指标
        quality_items = []
        business_items = []
        current_section = 'quality'
        
        for line in data_card:
            if '链接质量' in line or '链接质量指标' in line:
                current_section = 'quality'
                continue
            elif '生意指标' in line:
                current_section = 'business'
                continue
            elif line == '---':
                continue
            if current_section == 'quality':
                quality_items.append(line)
            else:
                business_items.append(line)
        
        if quality_items:
            st.markdown('<div style="font-size:0.85rem;color:#888;margin-bottom:0.3rem;">📊 链接质量指标</div>', unsafe_allow_html=True)
            for item in quality_items:
                st.markdown(f'<div class="data-card">{item}</div>', unsafe_allow_html=True)
        
        if business_items:
            st.markdown('<div style="font-size:0.85rem;color:#888;margin:0.5rem 0 0.3rem;">📈 生意指标（受流量结构影响）</div>', unsafe_allow_html=True)
            for item in business_items:
                st.markdown(f'<div class="data-card">{item}</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # ============================================================
    # 模块二：产品与体验诊断
    # ============================================================
    st.markdown("### 📦 产品与体验诊断")
    
    product_dims = [d for d in DIMENSIONS if d['layer'] == '产品端']
    
    # 产品端维度评分
    html = ''
    for d in product_dims:
        html += render_score_bar(d['id'], dims)
    st.markdown(html, unsafe_allow_html=True)
    
    # 退款风险
    refund_impact = {}
    if ad_diagnosis:
        refund_impact = ad_diagnosis.get('refund_impact', {})
    
    refund_rate = refund_impact.get('refund_rate') or result.get('refund_rate', 0)
    refund_severity = refund_impact.get('severity', '')
    refund_cause = refund_impact.get('refund_root_cause', '')
    
    if refund_rate and float(refund_rate) > 0:
        rc1, rc2 = st.columns(2)
        with rc1:
            st.metric("退款率", f"{float(refund_rate):.1f}%")
        with rc2:
            if refund_severity == 'severe':
                cause_text = {
                    'hybrid_plan_cart_stuffing': '全站推广凑单导致',
                    'traffic_imprecision': '流量不精准导致',
                }.get(refund_cause, '需退款明细数据排查原因')
                st.metric("退款风险", f"偏高 — {cause_text}")
            else:
                st.metric("退款风险", "正常")
    else:
        st.info("无退款率数据，无法判断退款风险。如需诊断退款问题，请提供含退款字段的推广报表。")
    
    # 月销基数
    monthly_sales = result.get('monthly_sales')
    if monthly_sales:
        if int(monthly_sales) < 50:
            st.warning(f"月销仅{int(monthly_sales)}件，自然流量飞轮未转起来，先拉销量基数")
        elif int(monthly_sales) < 200:
            st.info(f"月销{int(monthly_sales)}件，有一定基础但仍需提升")
        else:
            st.success(f"月销{int(monthly_sales)}件，销量基数健康")
    
    st.markdown("---")
    
    # ============================================================
    # 模块三：推广诊断
    # ============================================================
    if ad_diagnosis:
        st.markdown("### 💰 推广诊断")
        
        # 推广总览
        summary = ad_diagnosis.get('summary', {})
        if summary:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("推广总花费", f"¥{summary.get('total_cost', 0):,.0f}")
            with col2:
                surface_roi = summary.get('surface_roi', 0)
                real_roi = summary.get('real_roi', 0)
                st.metric("真实ROI", f"{real_roi:.2f}", delta=f"表面 {surface_roi:.2f}")
            with col3:
                if refund_rate:
                    st.metric("退款率", f"{float(refund_rate):.1f}%")
        
        # 推广深度数据卡片
        if ad_data_card:
            for line in ad_data_card:
                st.markdown(f'<div class="data-card">{line}</div>', unsafe_allow_html=True)
        
        # 拉新层
        launch = ad_diagnosis.get('launch_diagnosis', {})
        if launch and launch.get('status') != 'no_data':
            st.markdown("#### 🔵 拉新层")
            if launch.get('total_cost'):
                st.markdown(f"花费 ¥{launch['total_cost']:,.0f}，真实ROI {launch.get('real_roi', '?')}")
            best = launch.get('best_cart_plan')
            if best:
                st.markdown(f"**最佳蓄水**：{best.get('plan_name', '—')}")
                lc1, lc2, lc3 = st.columns(3)
                with lc1:
                    st.metric("加购率", f"{best.get('cart_rate', 0):.1f}%")
                with lc2:
                    st.metric("收藏加购成本", f"¥{best.get('fav_cart_cost', 0):.1f}")
                with lc3:
                    st.metric("真实ROI", f"{best.get('real_roi', 0):.2f}")
        
        # 收割层
        harvest = ad_diagnosis.get('harvest_diagnosis', {})
        if harvest:
            total_cost = harvest.get('total_cost', 0)
            if total_cost and total_cost > 0:
                st.markdown("#### 🟠 收割层")
                st.markdown(f"花费 ¥{total_cost:,.0f}，真实ROI {harvest.get('real_roi', '?')}")
                msg = harvest.get('message', '')
                if msg:
                    st.caption(msg)
            elif harvest.get('status') == 'no_data':
                st.markdown("#### 🟠 收割层")
                st.caption("无收割层计划数据")
        
        # 全站推广
        hybrid = ad_diagnosis.get('hybrid', {})
        if hybrid and hybrid.get('plans'):
            st.markdown("#### 🟣 全站推广")
            for plan in hybrid['plans']:
                st.markdown(f"**{plan.get('plan_name', '—')}**")
                hc1, hc2, hc3 = st.columns(3)
                with hc1:
                    st.metric("花费", f"¥{plan.get('cost', 0):,.0f}")
                with hc2:
                    st.metric("真实ROI", f"{plan.get('real_roi', 0):.2f}")
                with hc3:
                    st.metric("转化率", f"{plan.get('conv_rate', 0):.2f}%")
    else:
        st.markdown("### 💰 推广诊断")
        st.info("未上传推广报表，无法进行推广深度分析。上传阿里妈妈计划报表可解锁真实ROI、归因虚高、蓄水效率等诊断。")
    
    st.markdown("---")
    
    # ============================================================
    # 模块四：数据完整性提示
    # ============================================================
    _, missing = check_data_completeness(st.session_state.get('uploaded_file_names', []))
    if missing:
        st.markdown("### 📋 数据完整性")
        for m in missing:
            st.markdown(f"""
            <div class="data-missing">
                ⚠️ 缺少<b>{m['type']}</b>，无法诊断：{'、'.join(m['required_for'])}<br>
                <small>获取方式：{m['tip']}</small>
            </div>
            """, unsafe_allow_html=True)
    
    # ---- 术语说明（折叠） ----
    with st.expander("📖 术语说明"):
        for term, definition in GLOSSARY.items():
            st.markdown(f"**{term}** — {definition}")
    
    # ---- 商品信息 ----
    product_name = result.get('product_name', '')
    category = result.get('category', '')
    if product_name or category:
        col1, col2 = st.columns(2)
        with col1:
            st.caption(f"📦 商品：{product_name}")
        with col2:
            st.caption(f"🏷️ 品类：{category}")


# ============================================================
# 主页面
# ============================================================

# Header
st.markdown('<div class="main-header">📊 电商链接诊断</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">上传链接数据，增长专家帮你一针见血看问题</div>', unsafe_allow_html=True)

# 如果有诊断结果，展示报告
if st.session_state.diagnosis_result:
    result = st.session_state.diagnosis_result
    
    # 重新诊断按钮
    if st.button("🔄 重新诊断"):
        st.session_state.diagnosis_result = None
        st.session_state.parsed_data = None
        st.session_state.need_selection = False
        st.session_state.uploaded_file_names = []
        st.rerun()
    
    st.markdown("---")
    render_report(result)

# 如果需要选择商品
elif st.session_state.need_selection:
    st.markdown("---")
    st.markdown("### 🔍 推广报表检测到多个商品")
    st.markdown("请选择你要诊断的商品：")
    
    products = st.session_state.available_products
    selected = st.radio("选择商品", products, horizontal=True)
    
    if st.button("开始诊断", type="primary"):
        with st.spinner("正在运行诊断引擎..."):
            result = run_full_diagnosis(
                st.session_state.uploaded_files,
                product_prefix=selected
            )
            st.session_state.diagnosis_result = result
            st.session_state.need_selection = False
            st.rerun()

# 上传区域
else:
    st.markdown("---")
    
    # 使用说明
    st.markdown("""
    <div style="margin: 1rem 0;">
        <span class="step-badge">1</span> 上传3个生意参谋导出文件（商品概况 + 流量来源 + 推广报表）<br>
        <span class="step-badge">2</span> 系统自动解析数据、识别类目<br>
        <span class="step-badge">3</span> 诊断引擎18维度评分 + 推广深度分析 + 归因修正
    </div>
    """, unsafe_allow_html=True)
    
    # 文件上传
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**📦 商品概况**")
        st.caption("生意参谋 → 商品 → 商品概况")
        file1 = st.file_uploader(
            "商品概况文件",
            type=['csv', 'xls', 'xlsx'],
            key="file1",
            label_visibility="collapsed"
        )
    
    with col2:
        st.markdown("**🔄 流量来源**")
        st.caption("生意参谋 → 流量 → 商品二级来源")
        file2 = st.file_uploader(
            "流量来源文件",
            type=['csv', 'xls', 'xlsx'],
            key="file2",
            label_visibility="collapsed"
        )
    
    with col3:
        st.markdown("**💰 推广报表**")
        st.caption("阿里妈妈 → 计划报表")
        file3 = st.file_uploader(
            "推广报表文件",
            type=['csv', 'xls', 'xlsx'],
            key="file3",
            label_visibility="collapsed"
        )
    
    # 诊断按钮
    st.markdown("")
    
    # 检查文件上传状态
    files_ready = file1 is not None or file2 is not None or file3 is not None
    
    if files_ready:
        uploaded_files = []
        if file1:
            uploaded_files.append(file1)
        if file2:
            uploaded_files.append(file2)
        if file3:
            uploaded_files.append(file3)
        
        # 数据完整性预检
        file_names = [f.name for f in uploaded_files]
        found, missing = check_data_completeness(file_names)
        
        if missing:
            missing_types = '、'.join([m['type'] for m in missing])
            st.warning(f"已上传 {len(uploaded_files)} 个文件，但缺少：{missing_types}。部分诊断模块将无法运行。")
            with st.expander("查看缺少的数据及获取方式"):
                for m in missing:
                    st.markdown(f"- **{m['type']}**：无法诊断 {'、'.join(m['required_for'])}。获取方式：{m['tip']}")
        else:
            st.success(f"已上传 {len(uploaded_files)} 个文件，数据完整，可运行全量诊断")
        
        if st.button("🚀 开始诊断", type="primary", use_container_width=True):
            temp_dir = tempfile.mkdtemp()
            file_paths = []
            
            for f in uploaded_files:
                temp_path = os.path.join(temp_dir, f.name)
                with open(temp_path, 'wb') as out:
                    out.write(f.getbuffer())
                file_paths.append(temp_path)
            
            with st.spinner("正在解析文件并运行诊断引擎..."):
                progress = st.progress(0, text="解析文件中...")
                time.sleep(0.3)
                progress.progress(30, text="识别类目和商品...")
                time.sleep(0.3)
                progress.progress(60, text="运行18维度评分...")
                time.sleep(0.3)
                
                result = run_full_diagnosis(file_paths)
                
                progress.progress(100, text="诊断完成！")
                time.sleep(0.3)
            
            if isinstance(result, dict) and result.get('status') == 'need_selection':
                st.session_state.need_selection = True
                st.session_state.available_products = result['available_products']
                st.session_state.parsed_data = result.get('parsed_data')
                st.session_state.uploaded_files = file_paths
                st.session_state.uploaded_file_names = file_names
                st.rerun()
            else:
                st.session_state.diagnosis_result = result
                st.session_state.uploaded_files = file_paths
                st.session_state.uploaded_file_names = file_names
                st.rerun()
    
    else:
        st.markdown("""
        <div class="upload-zone">
            👆 请上传至少1个文件开始诊断<br>
            <small>支持 .csv / .xls / .xlsx 格式，推荐上传全部3个文件获得完整诊断</small>
        </div>
        """, unsafe_allow_html=True)
    
    # 底部说明
    st.markdown("---")
    st.caption("💡 数据安全：文件仅在你本地处理，不会上传到任何第三方服务器")
