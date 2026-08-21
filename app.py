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
import re
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
    {'id': 'traffic_quality',       'name': '流量质量精准度',  'layer': '流量端',
     'interpret': {
         (0, 4): '付费流量精准度差，大量花费在泛词和不相关人群上，先收缩关键词和人群包',
         (4, 6): '流量精准度一般，核心词有拿到但泛词也占了不少预算',
         (6, 8): '流量精准度良好，核心关键词和人群覆盖比较聚焦',
         (8, 11): '流量精准度很高，付费流量几乎都打在了对的人身上',
     }},
    {'id': 'position_rank',         'name': '位置排名',        'layer': '流量端',
     'interpret': {
         (0, 4): '核心词排名靠后，自然流量拿不到，高度依赖付费',
         (4, 6): '部分核心词有排名但不够靠前，自然流量还有提升空间',
         (6, 8): '核心词排名稳定，自然搜索能持续带来流量',
         (8, 11): '核心词排名靠前，自然流量基础扎实',
     }},
    {'id': 'time_node',             'name': '时间节点',        'layer': '流量端',
     'interpret': {
         (0, 4): '当前处于品类淡季或需求下行期，投放效率会打折扣，注意控制预算节奏',
         (4, 6): '品类需求平稳，没有明显的季节性红利，按常规节奏运营',
         (6, 8): '品类处于需求上升期，可以适当加大投放力度',
         (8, 11): '品类旺季/需求高峰期，正是放量抢份额的好时机',
     }},
    {'id': 'traffic_page_match',    'name': '流量承接效率', 'layer': '转化端',
     'interpret': {
         (0, 4): '拉新UV价值远低于点击成本，广告花1块赚不回0.8块，流量承接效率差',
         (4, 6): '拉新UV价值和点击成本接近，广告勉强打平。当推广占比过高时，承接效率低往往是流量精准度不足的结果（来的人不对），而非页面问题',
         (6, 8): '流量承接效率不错，UV价值高于点击成本，广告能赚钱',
         (8, 11): '流量承接效率很高，每花1块广告费能赚回1.5+，推广效益好',
     }},
    {'id': 'main_image_ctr',        'name': '主图点击率',      'layer': '转化端',
     'interpret': {
         (0, 4): '主图点击率远低于行业，在搜索结果页被竞品碾压，先优化主图',
         (4, 6): '主图点击率中等，有优化空间但不算硬伤',
         (6, 8): '主图点击率良好，搜索曝光能稳定拿到点击',
         (8, 11): '主图点击率优秀，搜索展示的点击转化能力强',
     }},
    {'id': 'detail_page_logic',     'name': '详情页五层逻辑',  'layer': '转化端',
     'interpret': {
         (0, 4): '详情页逻辑混乱，用户看不到核心卖点和购买理由，高跳失率的根因之一',
         (4, 6): '详情页有基本逻辑但说服力不够，缺少有力的信任背书或痛点击穿',
         (6, 8): '详情页逻辑清晰，用户能顺畅获取关键信息',
         (8, 11): '详情页说服力强，卖点层层递进，转化效率高',
     }},
    {'id': 'review_quality',        'name': '评价质量',        'layer': '转化端',
     'interpret': {
         (0, 4): '差评集中且未回复，严重影响新客购买决策，需紧急处理',
         (4, 6): '评价质量一般，部分差评未及时处理',
         (6, 8): '评价质量良好，好评率高且有带图评价',
         (8, 11): '评价优秀，口碑是转化的重要推动力',
     }},
    {'id': 'wen_dajia',             'name': '问大家',          'layer': '转化端',
     'interpret': {
         (0, 4): '问大家负面回复多，正在劝退潜在买家，需主动运营',
         (4, 6): '问大家有负面但影响可控',
         (6, 8): '问大家运营良好，多数问题有正面回复',
         (8, 11): '问大家是转化助力，买家回复积极正面',
     }},
    {'id': 'customer_service',      'name': '客服询单转化',    'layer': '转化端',
     'interpret': {
         (0, 4): '客服询单转化率低，来了咨询也成交不了，话术和响应速度都要改',
         (4, 6): '客服转化率中等，话术有优化空间',
         (6, 8): '客服转化率良好，能抓住咨询成交',
         (8, 11): '客服转化率优秀，是成交的重要保障',
     }},
    {'id': 'market_acceptance',     'name': '市场接受度',      'layer': '产品端',
     'interpret': {
         (0, 4): '市场接受度低，用户看了不买不收藏，可能选品或定价有问题',
         (4, 6): '市场接受度一般，有浏览意愿但购买意愿不够强',
         (6, 8): '市场接受度良好，用户对产品有兴趣且愿意下单',
         (8, 11): '市场接受度高，产品自带流量和转化能力',
     }},
    {'id': 'price_positioning',     'name': '价格定位',        'layer': '产品端',
     'interpret': {
         (0, 4): '价格定位偏高或偏低，偏离市场主流接受区间，影响转化',
         (4, 6): '价格定位中等，不是优势也不是短板',
         (6, 8): '价格定位合理，在同类竞品中有竞争力',
         (8, 11): '价格定位精准，高性价比是核心卖点',
     }},
    {'id': 'sku_coverage',          'name': 'SKU覆盖',         'layer': '产品端',
     'interpret': {
         (0, 4): 'SKU覆盖不足，大量零动销SKU浪费权重，核心SKU也可能缺失',
         (4, 6): 'SKU覆盖一般，部分零动销SKU需要清理',
         (6, 8): 'SKU覆盖良好，主力SKU动销稳定',
         (8, 11): 'SKU矩阵精准，每个SKU都在贡献销量',
     }},
]

# 术语表
GLOSSARY = {
    '搜索转化率': '用户通过搜索关键词进入商品页后成交的比例，反映链接本身的真实转化能力',
    '蓄水效率': '广告花钱换来的收藏加购意愿，加购率高=蓄水好，用户在观望等待购买时机',
    'ROI': '广告投入产出比，直接使用阿里妈妈平台给出的ROI数据',
    '表面ROI': '报表上直接显示的ROI，包含了自然流量成交被算到广告头上的部分',
    '归因虚高': '平台归因机制说明，仅供参考',
    '加购率': '点击广告后加入购物车的比例，高加购率=用户有意向但可能在比价',
    '收藏加购成本': '获得一个收藏或加购需要花多少广告费，越低蓄水越高效',
    '拉新层': '以获取新客户为主要目标的推广计划',
    '收割层': '以触达已收藏/加购/浏览过但未购买用户为主的推广计划',
    '全站推广': '同时覆盖拉新和收割的混合型推广计划，不拆分统计',
    '跳失率': '进入页面后没有任何操作就离开的比例，但广告占比高时跳失率高不代表页面差',
    '广告占比': '付费流量占总流量的比例，超过70%时整体指标会被稀释',
    'UV价值': '每个广告点击带来的综合价值，拉新层=直接成交价值+蓄水价值，收割层=直接成交价值',
    '蓄水价值': '广告带来的加购用户未来回店成交的预期价值=加购率×回店率×客单价',
    '回店率': '购物车渠道访客数÷加购人数，反映加购用户后续回店的比例',
    'UV效率': 'UV价值÷CPC，衡量每花1元广告费换来多少UV价值，<0.8=亏，≥1.5=赚',
    '流量承接效率': '衡量广告流量被页面承接并转化的效率，用UV效率替代旧的匹配度评分',
}

# 低分维度排查步骤（分数<5时显示）
TROUBLESHOOT = {
    'traffic_page_match': [
        '查看UV价值对比：拉新层UV价值 < 点击成本CPC -> 广告引来的流量接不住',
        '拉新效率低的原因：1.广告定向太泛引来错的人 2.页面没接住广告承诺的卖点',
        '如果加购率低->改定向/关键词收窄人群；如果加购率高但转化低->优化页面承接',
    ],
    'traffic_quality': [
        '导出直通车/引力魔方关键词报表，按花费降序排列',
        '标记与产品核心卖点无关的泛词（如"净水器"vs"家用直饮净水器"）',
        '泛词降价或暂停，预算挪到精准长尾词上',
    ],
    'main_image_ctr': [
        '搜索核心关键词，截图前5名竞品主图',
        '对比自己主图与竞品的差异化：谁更抓眼球？卖点是否清晰？',
        'A/B测试：换一张突出核心卖点的主图，观察3天点击率变化',
    ],
    'review_quality': [
        '导出近30天差评，按原因分类（质量/物流/描述不符/其他）',
        '针对TOP3差评原因，在详情页增加对应内容（如质量质疑→加质检报告）',
        '回复所有差评，展示解决态度',
    ],
    'position_rank': [
        '在生意参谋搜索分析中，导出核心词的搜索人气和你的排名',
        '排名不在前3页的词，短期靠直通车卡位，中期靠销量权重提升',
        '优先攻占搜索人气高但竞争度适中的长尾词',
    ],
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
        'required_for': ['ROI', '蓄水效率', '加购率'],
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
# 密码保护
# ============================================================
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown('<div style="text-align:center;padding:3rem 1rem;"><h1 style="font-size:2rem;color:#1a1a2e;">🔒 电商链接诊断</h1><p style="color:#666;margin-bottom:2rem;">请输入访问密码</p></div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        pwd = st.text_input("密码", type="password")
        if st.button("进入系统"):
            if pwd == "guanfu2026":
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("密码错误，请联系管理员获取访问权限")
    st.stop()


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


def get_dim_interpret(dim_def, score):
    """根据维度定义和分数返回一句话解读"""
    if score is None or 'interpret' not in dim_def:
        return ''
    for (low, high), text in dim_def['interpret'].items():
        if low <= score < high:
            return text
    return ''

def get_dim_def(dim_id):
    """根据id获取维度定义"""
    for d in DIMENSIONS:
        if d['id'] == dim_id:
            return d
    return {}

def render_score_bar(dim_id, dims):
    """渲染单个维度的评分条+解读"""
    dr = dims.get(dim_id, {})
    score = dr.get('score')
    name = get_dim_def(dim_id).get('name') or dr.get('name', dim_id)
    dim_def = get_dim_def(dim_id)
    
    if score is not None:
        color = score_color(score)
        width = max(score * 10, 5)
        label = score_label(score)
        interpret = get_dim_interpret(dim_def, score)
        interpret_html = f'<div style="font-size:0.8rem;color:#666;margin:0.1rem 0 0.3rem 130px;">💡 {interpret}</div>' if interpret else ''
        # 低分维度显示排查步骤
        troubleshoot_html = ''
        if score < 5 and dim_id in TROUBLESHOOT:
            steps = TROUBLESHOOT[dim_id]
            steps_str = ' → '.join([f'{i+1}.{s}' for i, s in enumerate(steps)])
            troubleshoot_html = f'<div style="font-size:0.78rem;color:#005FD3;margin:0.1rem 0 0.5rem 130px;">🔧 排查：{steps_str}</div>'
        return f"""
        <div style="display:flex;align-items:center;margin:0.3rem 0;">
            <div style="width:120px;font-size:0.9rem;color:#333;">{name}</div>
            <div style="flex:1;">
                <div class="score-bar"><div class="score-fill" style="width:{width}%;background:{color};"></div></div>
            </div>
            <div style="width:60px;text-align:right;font-size:0.9rem;font-weight:600;color:{color};">{score}/10 <span style="font-size:0.75rem;font-weight:400;">{label}</span></div>
        </div>
        {interpret_html}
        {troubleshoot_html}
        """
    else:
        source = dr.get('data_source', 'missing')
        source_hint = ''
        if source == 'missing':
            source_hint = '（生意参谋未导出此数据）'
        return f"""
        <div style="display:flex;align-items:center;margin:0.3rem 0;">
            <div style="width:120px;font-size:0.9rem;color:#999;">{name}</div>
            <div style="flex:1;"><div class="score-bar"><div class="score-fill" style="width:0%;background:#ccc;"></div></div></div>
            <div style="width:60px;text-align:right;font-size:0.9rem;color:#999;">— <span style="font-size:0.7rem;">{source_hint}</span></div>
        </div>
        """


# ============================================================
# 诊断函数
# ============================================================
def calc_uv_value(ad_diagnosis, cart_fav_visitors=None, total_cart=None):
    """计算各层UV价值，替代流量承接效率评分

    核心逻辑：
    - 回店率 = 购物车渠道访客数(仅购物车) / 全链接加购人数
    - 客单价 = 推广成交 / 推广成交笔数
    - 拉新层UV价值 = 直接成交价值 + 蓄水价值(加购率 x 回店率 x 客单价)
    - 收割层UV价值 = 真实成交/点击（收割不蓄水）
    - 效率 = UV价值 / CPC
    """
    result = {}
    if not ad_diagnosis:
        return result

    # ---- 拉新层 ----
    launch = ad_diagnosis.get('launch_diagnosis', {})
    launch_plans = launch.get('ranked_plans', []) or []
    launch_cost = launch.get('total_cost', 0) or sum(p.get('cost', 0) or 0 for p in launch_plans)
    launch_clicks = sum(p.get('clicks', 0) or 0 for p in launch_plans)
    launch_sales = launch.get('total_sales', 0) or sum(p.get('total_sales', 0) or 0 for p in launch_plans)
    launch_natural = sum(p.get('natural_sales', 0) or 0 for p in launch_plans)
    launch_fav_cart = sum(p.get('fav_cart_count', 0) or 0 for p in launch_plans)
    launch_orders = sum(p.get('total_orders', 0) or 0 for p in launch_plans)
    launch_cpc = round(launch_cost / launch_clicks, 2) if launch_clicks > 0 else None

    # ---- 收割层 ----
    harvest = ad_diagnosis.get('harvest_diagnosis', {})
    harvest_plans = (harvest.get('qualified_plans', []) or []) + (harvest.get('weak_plans', []) or []) + (harvest.get('waste_plans', []) or [])
    harvest_cost = harvest.get('total_cost', 0) or sum(p.get('cost', 0) or 0 for p in harvest_plans)
    harvest_clicks = sum(p.get('clicks', 0) or 0 for p in harvest_plans)
    harvest_sales = harvest.get('total_sales', 0) or sum(p.get('total_sales', 0) or 0 for p in harvest_plans)
    harvest_natural = sum(p.get('natural_sales', 0) or 0 for p in harvest_plans)
    harvest_cpc = round(harvest_cost / harvest_clicks, 2) if harvest_clicks > 0 else None

    # ---- 客单价（优先推广数据） ----
    avg_price = None
    total_orders_all = sum(p.get('total_orders', 0) or 0 for p in launch_plans) + sum(p.get('total_orders', 0) or 0 for p in harvest_plans)
    total_sales_all = launch_sales + harvest_sales
    if total_orders_all and total_orders_all > 0:
        avg_price = round(total_sales_all / total_orders_all, 2)
    elif launch_orders and launch_orders > 0:
        avg_price = round(launch_sales / launch_orders, 2)
    # 兜底：用推广总成交/月销推算
    summary = ad_diagnosis.get('summary', {})
    if avg_price is None and summary.get('total_cost') and launch_sales:
        # 用推广花费和ROI反推客单价（粗估）
        pass  # 暂不加兜底，先看主逻辑能否工作

    # ---- 回店率 ----
    return_rate = None
    if cart_fav_visitors and total_cart and total_cart > 0:
        return_rate = round(cart_fav_visitors / total_cart, 4)

    # ---- 拉新层UV价值 ----
    launch_uv_value = None
    launch_direct_value = None
    launch_water_value = None
    if launch_clicks > 0:
        launch_real_sales = launch_sales - launch_natural
        launch_direct_value = round(launch_real_sales / launch_clicks, 2)
        # 蓄水价值 = 加购率 x 回店率 x 客单价
        if return_rate is not None and avg_price and launch_plans:
            avg_cart_rate = sum(p.get('cart_rate', 0) or 0 for p in launch_plans) / len(launch_plans) if launch_plans else 0
            launch_water_value = round(avg_cart_rate / 100 * return_rate * avg_price, 2)
        launch_uv_value = launch_direct_value + (launch_water_value or 0)

    # ---- 收割层UV价值 ----
    harvest_uv_value = None
    if harvest_clicks > 0:
        harvest_real_sales = harvest_sales - harvest_natural
        harvest_uv_value = round(harvest_real_sales / harvest_clicks, 2)

    # ---- 效率判定 ----
    launch_roi = round(launch_uv_value / launch_cpc, 2) if launch_uv_value and launch_cpc and launch_cpc > 0 else None
    harvest_roi = round(harvest_uv_value / harvest_cpc, 2) if harvest_uv_value and harvest_cpc and harvest_cpc > 0 else None

    return {
        'avg_price': avg_price,
        'return_rate': return_rate,
    'return_rate_display': min(return_rate, 1.0) if return_rate is not None else None,
        'launch': {
            'uv_value': launch_uv_value,
            'direct_value': launch_direct_value,
            'water_value': launch_water_value,
            'cpc': launch_cpc,
            'roi': launch_roi,
            'clicks': launch_clicks,
            'cost': launch_cost,
            'roi': round(launch_sales / launch_cost, 2) if launch_cost and launch_cost > 0 else None,
        },
        'harvest': {
            'uv_value': harvest_uv_value,
            'cpc': harvest_cpc,
            'roi': harvest_roi,
            'clicks': harvest_clicks,
            'cost': harvest_cost,
            'roi': round(harvest_sales / harvest_cost, 2) if harvest_cost and harvest_cost > 0 else None,
        },
    }


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


# ============================================================
# 人货匹配深度分析
# ============================================================
# 品类核心关注点（访客最在意的卖点维度）
CATEGORY_KEY_SELLING_POINTS = {
    '净水壶': ['过滤效果', '安装便捷', '滤芯成本', '品牌信任', '售后保障', '出水速度'],
    '净水器': ['过滤效果', '安装便捷', '滤芯成本', '品牌信任', '售后保障', '出水速度'],
    '女装': ['款式设计', '面料质感', '尺码准确', '颜色还原', '性价比'],
    '食品': ['口味', '新鲜度', '配料安全', '性价比', '包装'],
    '3C数码': ['性能参数', '品牌', '售后', '性价比', '外观'],
}

# 推广计划名中的定向类型关键词
TRAFFIC_TYPE_KEYWORDS = {
    '关键词定向': ['关键词', '搜索', '趋势明星', '广泛', '精准', '长词'],
    '人群定向': ['人群', '相似', '拉新', '重定向', '收割', '老客', '新客', '资产'],
    '内容/短视频': ['短视频', '内容', '直播', '逛逛', '超级短视频'],
    '全站推广': ['全站'],
}


def _classify_traffic_type(plan_name):
    """从计划名判断定向类型"""
    for t, keywords in TRAFFIC_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in plan_name:
                return t
    return '关键词定向'  # 默认归为关键词定向


def analyze_visitor_product_match(result, ad_diagnosis):
    """人货匹配深度分析：访客画像 × 页面/产品定位 → 匹配度 + 改进空间"""
    analysis = {}
    
    # ---- 1. 访客侧画像 ----
    data_card = result.get('data_card', [])
    
    ad_traffic_ratio = None
    for line in data_card:
        if '广告流量占比' in line:
            try:
                raw = float(''.join(c for c in line.split('：')[-1] if c.isdigit() or c == '.'))
                # 兼容：可能是88(百分比)或0.88(小数)
                ad_traffic_ratio = raw / 100 if raw > 1 else raw
            except: pass
    
    visitor_profile = {}
    if ad_traffic_ratio and ad_traffic_ratio > 0.7:
        visitor_profile['dominant_channel'] = '付费广告'
        visitor_profile['dominant_ratio'] = f'{ad_traffic_ratio*100:.0f}%'
        visitor_profile['user_type'] = '被广告触达的被动型用户为主'
    elif ad_traffic_ratio and ad_traffic_ratio > 0.4:
        visitor_profile['dominant_channel'] = '付费+自然混合'
        visitor_profile['dominant_ratio'] = f'{ad_traffic_ratio*100:.0f}%'
        visitor_profile['user_type'] = '主动搜索+被动触达混合型用户'
    else:
        visitor_profile['dominant_channel'] = '自然流量'
        visitor_profile['dominant_ratio'] = f'{(ad_traffic_ratio or 0)*100:.0f}%'
        visitor_profile['user_type'] = '主动搜索型用户为主'
    analysis['visitor_profile'] = visitor_profile
    
    # ---- 2. 从推广计划提取定向类型 ----
    plan_types = {'关键词定向': 0, '人群定向': 0, '内容/短视频': 0, '全站推广': 0}
    plan_details = []
    
    if ad_diagnosis:
        launch = ad_diagnosis.get('launch_diagnosis', {})
        for p in launch.get('worst_plans', []):
            ptype = _classify_traffic_type(p.get('plan_name', ''))
            plan_types[ptype] = plan_types.get(ptype, 0) + p.get('cost', 0)
            plan_details.append({
                'name': p.get('plan_name', ''), 'type': ptype, 'cost': p.get('cost', 0),
                'cart_rate': p.get('cart_rate'), 'surface_roi': p.get('surface_roi'),
                'launch_score': p.get('launch_score'), 'layer': '拉新',
            })
        best = launch.get('best_cart_plan')
        if best:
            ptype = _classify_traffic_type(best.get('plan_name', ''))
            plan_types[ptype] = plan_types.get(ptype, 0) + best.get('cost', 0)
            plan_details.append({
                'name': best.get('plan_name', ''), 'type': ptype, 'cost': best.get('cost', 0),
                'cart_rate': best.get('cart_rate'), 'surface_roi': best.get('surface_roi'),
                'launch_score': best.get('launch_score', 10), 'layer': '拉新',
            })
        harvest = ad_diagnosis.get('harvest_diagnosis', {})
        for p in harvest.get('plans', []):
            ptype = _classify_traffic_type(p.get('plan_name', ''))
            plan_types[ptype] = plan_types.get(ptype, 0) + p.get('cost', 0)
            plan_details.append({
                'name': p.get('plan_name', ''), 'type': ptype, 'cost': p.get('cost', 0),
                'cart_rate': p.get('cart_rate'), 'surface_roi': p.get('surface_roi'), 'layer': '收割',
            })
        hybrid = ad_diagnosis.get('hybrid', {})
        for p in hybrid.get('plans', []):
            ptype = _classify_traffic_type(p.get('plan_name', ''))
            plan_types[ptype] = plan_types.get(ptype, 0) + p.get('cost', 0)
            plan_details.append({
                'name': p.get('plan_name', ''), 'type': ptype, 'cost': p.get('cost', 0),
                'cart_rate': p.get('cart_rate'), 'surface_roi': p.get('surface_roi'), 'layer': '全站',
            })
    
    analysis['plan_types'] = {k: v for k, v in plan_types.items() if v > 0}
    analysis['plan_details'] = plan_details
    
    # ---- 3. 匹配度判断 ----
    match_verdict = ''
    improvements = []
    
    if plan_types:
        top_type = max(plan_types, key=plan_types.get)
        top_cost = plan_types[top_type]
        total_ad_cost = sum(plan_types.values()) or 1
        
        if top_type == '全站推广' and top_cost / total_ad_cost > 0.6:
            match_verdict = '推广以全站推广为主，无法区分拉新/收割，人货匹配无法精准调优'
            improvements.append('拆分全站推广为独立的拉新计划+收割计划，才能精准匹配不同人群')
        elif top_type == '关键词定向':
            low_score_plans = [p for p in plan_details if p.get('launch_score') and p['launch_score'] < 4 and p['layer'] == '拉新']
            if low_score_plans:
                match_verdict = f'关键词定向占比最高，但{len(low_score_plans)}个计划蓄水效率低——引来的搜索用户和页面不匹配'
                improvements.append('低效关键词计划：换更精准的词（如"台下式直饮净水器"替代"净水器"），或改页面承接搜索意图')
            else:
                match_verdict = '关键词定向为主，用户主动搜索进来的，匹配度基础较好'
        elif top_type == '人群定向':
            best_plan = max(plan_details, key=lambda x: x.get('cart_rate') or 0) if plan_details else None
            if best_plan and best_plan.get('cart_rate') and best_plan['cart_rate'] > 5:
                match_verdict = '人群定向为主，最佳计划加购率较高，人群匹配度不错'
            else:
                match_verdict = '人群定向为主，但加购率普遍偏低，人群包可能太泛或不够精准'
                improvements.append('收缩人群包：从泛人群收窄到"近30天浏览未购买"或"同类商品加购未买"等高意向人群')
        elif top_type == '内容/短视频':
            match_verdict = '内容/短视频为主，用户被动触达，对产品认知浅，需要页面快速建立信任'
            improvements.append('短视频引流→页面首屏必须和视频卖点一致，3秒内让用户确认"这就是我要的"')
    
    dims = result.get('dim_results', {})
    tpm = dims.get('traffic_page_match', {}).get('score')
    _uv = result.get('_uv_value', {})
    launch_roi = _uv.get('launch', {}).get('roi')
    if (tpm is not None and tpm < 5 and launch_roi is None):
        if not match_verdict:
            match_verdict = '流量承接效率低，访客和页面存在明显错位'
        low_plans = [p for p in plan_details if p.get('launch_score') and p['launch_score'] < 4]
        if low_plans:
            low_names = '、'.join([p['name'][:15] + '...' if len(p['name']) > 15 else p['name'] for p in low_plans[:3]])
            improvements.append(f'低匹配计划：{low_names}——这些计划花钱引来的用户对页面内容没兴趣')
    
    # ---- 4. 品类卖点匹配 ----
    category = result.get('category', '')
    key_points = CATEGORY_KEY_SELLING_POINTS.get(category, [])
    if key_points and plan_details:
        product_title = result.get('product_title', '') or result.get('product_name', '')
        plan_names_text = product_title + ' ' + ' '.join([p['name'] for p in plan_details])
        covered_points = []
        uncovered_points = []
        point_keywords = {
            '过滤效果': ['过滤', '净化', '直饮', 'RO', '反渗透', '净水'],
            '安装便捷': ['安装', '免安装', '台下', '厨下', '台上'],
            '滤芯成本': ['滤芯', '替换', '耗材'],
            '品牌信任': ['品牌', '旗舰店', '官方'],
            '售后保障': ['售后', '质保', '保修', '包安装'],
            '出水速度': ['大通量', '出水', '流量', '600G', '800G', '1000G'],
            '款式设计': ['新款', '设计', '风格', '时尚'],
            '面料质感': ['面料', '材质', '纯棉', '真丝'],
            '尺码准确': ['尺码', '版型'],
            '性价比': ['性价比', '平替', '实惠', '优惠'],
        }
        for point in key_points:
            keywords = point_keywords.get(point, [point])
            if any(kw in plan_names_text for kw in keywords):
                covered_points.append(point)
            else:
                uncovered_points.append(point)
        if uncovered_points:
            improvements.append(f'广告未覆盖的品类核心卖点：{"、".join(uncovered_points[:3])}——这些可能是用户最在意但你没讲的')
        analysis['covered_selling_points'] = covered_points
        analysis['uncovered_selling_points'] = uncovered_points
        analysis['_debug_product_title'] = product_title[:80] if product_title else '(empty)'
        analysis['_debug_plan_names'] = ', '.join([p['name'] for p in plan_details[:5]])
    
    analysis['match_verdict'] = match_verdict
    analysis['improvements'] = improvements
    return analysis


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

    # 计算UV价值（替代流量承接效率AI评分）
    cart_fav_v = result.get('cart_fav_visitors')
    _uv_data = calc_uv_value(ad_diagnosis, cart_fav_v, result.get("total_cart"))
    result['_uv_value'] = _uv_data
    result['_uv_value']['cart_fav_visitors'] = result.get('cart_fav_visitors')
    result['_uv_value']['total_cart'] = result.get('total_cart')
    # 用UV效率覆盖旧的tpm_score（有推广数据时）
    _launch_roi = _uv_data.get('launch', {}).get('roi')
    if _launch_roi is not None:
        _tpm_dims = result.get('dim_results', {})
        if 'traffic_page_match' in _tpm_dims:
            if _launch_roi < 0.8:
                _tpm_dims['traffic_page_match']['score'] = 3.0
            elif _launch_roi < 3.0:
                _tpm_dims['traffic_page_match']['score'] = 5.0
            else:
                _tpm_dims['traffic_page_match']['score'] = 7.0
    
    # ============================================================
    # 总览：跨模块因果分析
    # ============================================================
    
    # 收集各模块关键信号
    surface_roi = None
    total_cost = 0
    best_cart_plan_name = ''
    best_cart_rate = 0
    best_cart_roi = 0
    
    if ad_diagnosis:
        summary = ad_diagnosis.get('summary', {})
        surface_roi = summary.get('surface_roi', 0)
        total_cost = summary.get('total_cost', 0)
        best_cart = ad_diagnosis.get('launch_diagnosis', {}).get('best_cart_plan')
        if best_cart:
            best_cart_plan_name = best_cart.get('plan_name', '')
            best_cart_rate = best_cart.get('cart_rate', 0)
            best_cart_roi = best_cart.get('surface_roi', 0)
    
    # 直接从 result 对象取值，不依赖文本解析（文本解析在多百分数时会拼错如1.923.0）
    raw_ad_ratio = result.get('ad_traffic_ratio')
    raw_natural_conv = result.get('natural_conv_rate')
    
    ad_ratio = None
    natural_conv = None
    
    # 处理 ad_ratio：可能是小数(0.88)或百分数(88)
    if raw_ad_ratio is not None:
        try:
            val = float(raw_ad_ratio)
            ad_ratio = val * 100 if val < 1 else val  # 0.88 → 88
        except:
            pass
    
    # 处理 natural_conv：直接是数字
    if raw_natural_conv is not None:
        try:
            natural_conv = float(raw_natural_conv)
        except:
            pass
    
    # 兜底：如果 result 对象没取到，再从 data_card 文本解析（修复多百分数拼接问题）
    if ad_ratio is None or natural_conv is None:
        for line in data_card:
            if ad_ratio is None and '广告流量占比' in line:
                try:
                    ad_ratio = float(''.join(c for c in line.split('：')[-1] if c.isdigit() or c == '.'))
                except:
                    pass
            if natural_conv is None and '搜索转化率' in line:
                for part in line.split('：'):
                    if '%' in part:
                        try:
                            first_pct = part.split('%')[0]
                            natural_conv = float(''.join(c for c in first_pct if c.isdigit() or c == '.'))
                        except:
                            pass
                        break
    
    refund_impact = ad_diagnosis.get('refund_impact', {}) if ad_diagnosis else {}
    refund_rate = refund_impact.get('refund_rate') or result.get('refund_rate', 0)
    refund_rate = float(refund_rate) if refund_rate else 0
    
    scored_dims = {k: v for k, v in dims.items() if v.get('score') is not None}
    tpm_score = scored_dims.get('traffic_page_match', {}).get('score')  # 旧匹配度评分（兜底用）
    tq_score = scored_dims.get('traffic_quality', {}).get('score')      # 流量质量精准度

    # ---- UV价值数据（替代流量承接效率AI评分） ----
    launch_uv = _uv_data.get('launch', {})
    harvest_uv = _uv_data.get('harvest', {})
    launch_roi = launch_uv.get('roi')   # 拉新层ROI
    harvest_roi = harvest_uv.get('roi')  # 收割层ROI
    
    # ---- 跨模块因果分析 ----
    core_issue = ''       # 核心矛盾
    evidence = []         # 证据链
    priorities = []       # 优先方向（编号）
    
    # ---- 四维度分档（决定核心矛盾方向） ----
    # 流量承接效率：<4差，4-6一般，>6 OK

    # 流量承接效率（替代原流量承接效率评分）：
    #   效率<0.8 -> 承接差（花1块赚不回0.8块）
    #   效率0.8~1.5 -> 承接一般
    #   效率>=1.5 -> 承接好（花1块赚回1.5+）
    # 无推广数据时回退到原tpm_score
    if launch_roi is not None:
        tpm_bad = launch_roi < 2.0
        tpm_mid = 2.0 <= launch_roi < 3.0
        tpm_ok = launch_roi >= 3.0
    else:
        tpm_bad = tpm_score is not None and tpm_score < 4
        tpm_mid = tpm_score is not None and 4 <= tpm_score < 6
        tpm_ok = tpm_score is not None and tpm_score >= 6

    # 效率描述（用于证据链文案）
    if launch_roi is not None and launch_uv.get('cpc'):
        eff_brief = f"拉新ROI {launch_roi:.2f}"
    elif tpm_score is not None:
        eff_brief = f"流量承接效率{tpm_score}/10"
    else:
        eff_brief = "流量承接效率未知"

    
    # 付费占比：<40%健康，40-70%偏高，>70%重度依赖
    ad_heavy = ad_ratio is not None and ad_ratio > 70
    ad_high = ad_ratio is not None and 40 < ad_ratio <= 70
    ad_healthy = ad_ratio is not None and ad_ratio <= 40
    
    # 搜索转化率：<2%差，2-3%一般，>3%好
    search_conv_good = natural_conv is not None and natural_conv >= 3
    search_conv_mid = natural_conv is not None and 2 <= natural_conv < 3
    search_conv_weak = natural_conv is not None and natural_conv < 2
    search_conv_unknown = natural_conv is None
    
    # ROI：<1.5亏损，1.5-3中等，>3健康
    roi_losing = surface_roi is not None and surface_roi < 2.0
    roi_mid = surface_roi is not None and 2.0 <= surface_roi < 3
    roi_healthy = surface_roi is not None and surface_roi >= 3
    
    # 搜索转化率安全格式化
    conv_str = f"{natural_conv:.2f}" if natural_conv is not None else "未知"

    # ---- 退款率作为加重因子（不主导核心矛盾，但影响措辞和优先级） ----
    refund_crisis = refund_rate > 40
    refund_warning = refund_rate > 30 and not refund_crisis
    
    # 退款率对结论的加重程度描述
    if refund_crisis:
        refund_severity = "偏高"
        refund_hint = f"（退款率{refund_rate:.1f}%偏高（含平台满减凑单因素，仅供参考））"
        refund_action_hint = ""
    elif refund_warning:
        refund_severity = "偏高"
        refund_hint = f"（含平台满减凑单因素，退款率{refund_rate:.1f}%偏高）"
        refund_action_hint = ""
    else:
        refund_severity = "正常"
        refund_hint = ""
        refund_action_hint = ""

    # ---- 核心矛盾判定：流量承接效率 + 付费占比 + 搜索转化率 + ROI 四维度交叉 ----
    
    # ========== 流量承接差 + 重度付费 ==========
    if tpm_bad and ad_heavy:
        if roi_losing:
            if search_conv_weak:
                core_issue = "页面接不住付费流量，推广ROI偏低，转化也差"
                evidence.append(
                    f"{eff_brief} + {ad_ratio:.0f}%付费"
                    f"+ ROI {surface_roi:.2f} + 搜索转化率仅{conv_str}% → "
                    "页面承接不住广告流量，转化差推广还在亏，三重打击"
                )
            elif search_conv_mid:
                core_issue = "页面接不住付费流量，推广ROI偏低"
                evidence.append(
                    f"{eff_brief} + {ad_ratio:.0f}%付费"
                    f"+ ROI {surface_roi:.2f} → 页面没接住广告流量，推广费在浪费"
                )
            elif search_conv_unknown:
                core_issue = "页面接不住付费流量，推广ROI偏低"
                evidence.append(
                    f"{eff_brief} + {ad_ratio:.0f}%付费"
                    f"+ ROI {surface_roi:.2f} → 流量承接差+推广ROI偏低，搜索转化数据缺失"
                )
            else:
                core_issue = "页面接不住付费流量，推广ROI低"
                evidence.append(
                    f"{eff_brief} + {ad_ratio:.0f}%付费"
                    f"+ ROI {surface_roi:.2f} + 搜索转化率{conv_str}% → "
                    "搜索转化还行但流量承接差，推广结构ROI低"
                )
            if surface_roi < 1.0:
                priorities.append("🔴 先砍掉ROI为负的广告计划止损")
            else:
                priorities.append("🔴 先优化ROI偏低的广告计划，降低低效花费")
            priorities.append("再修流量承接效率——对齐广告创意与详情页卖点")
        
        elif roi_mid:
            if search_conv_weak:
                core_issue = "页面接不住流量，转化链路全面偏弱"
                evidence.append(
                    f"{eff_brief} + {ad_ratio:.0f}%付费"
                    f"+ 搜索转化率仅{conv_str}% → "
                    "页面没接住广告流量，自然搜索转化也差，整个承接链路都有问题"
                )
            elif search_conv_mid:
                core_issue = "广告承诺与产品体验脱节"
                evidence.append(
                    f"{eff_brief} + {ad_ratio:.0f}%付费"
                    f"+ 搜索转化率{conv_str}%（偏低）→ "
                    "广告引来的流量和页面/产品不匹配，搜索转化也不够强"
                )
            elif search_conv_unknown:
                core_issue = "广告承诺与产品体验脱节"
                evidence.append(
                    f"{eff_brief} + {ad_ratio:.0f}%付费"
                    f"+ ROI {surface_roi:.2f} → "
                    "流量承接差，广告流量接不住，搜索转化数据缺失无法进一步定位"
                )
            else:
                # search_conv_good: 搜索转化好说明产品有吸引力，问题偏广告流量匹配
                core_issue = "广告引来的流量和页面不匹配"
                evidence.append(
                    f"{eff_brief} + 搜索转化率{conv_str}%（不错）→ "
                    "产品本身有吸引力（搜索转化好），但广告引来的流量和页面/卖点不匹配，付费效率被拖低"
                )
            priorities.append("先对齐广告创意与详情页卖点，让进来的流量接得住")
            priorities.append("解决承接问题后，逐步把省下的预算投到搜索权重提升上")
        
        elif roi_healthy:
            core_issue = "流量承接效率拖了后腿，但推广ROI还行"
            evidence.append(
                f"{eff_brief} + ROI {surface_roi:.2f} → "
                "推广能赚钱，但流量承接效率差意味着转化率有提升空间，修好ROI还能更高"
            )
            priorities.append("优化流量承接效率，ROI提升空间大")
    
    # ========== 流量承接差 + 付费占比不高 ==========
    elif tpm_bad and not ad_heavy:
        if search_conv_weak:
            core_issue = "流量承接差 + 转化弱，自然流量也接不住"
            evidence.append(
                f"{eff_brief} + 搜索转化率仅{conv_str}% → "
                "页面没接住流量，自然搜索转化也差，形成恶性循环"
            )
            priorities.append("优化流量承接效率和详情页卖点承接")
            priorities.append("提升搜索转化率是突破关键")
        else:
            core_issue = "页面承接不住流量"
            evidence.append(f"{eff_brief} → 页面没接住流量")
            if refund_severity != "正常":
                evidence.append(f"退款率{refund_rate:.1f}%{refund_hint}，天猫平台满减凑单现象普遍，未发货退款占比高时多为凑单行为，不代表链接质量问题")
            priorities.append("解决流量承接效率——对齐广告创意与详情页卖点")
    
    # ========== 流量承接OK + 重度付费 + 转化差 ==========
    elif not tpm_bad and ad_heavy and search_conv_weak:
        if roi_losing:
            core_issue = "自然转化弱 + 推广在亏，停投就断流"
            evidence.append(
                f"{ad_ratio:.0f}%付费 + 搜索转化率仅{conv_str}%"
                f"+ ROI {surface_roi:.2f} → 自然转化不行，付费又在亏，进退两难"
            )
            priorities.append("先砍亏损计划止损，保住现金流")
            priorities.append("再从标题、关键词、评价入手提升搜索转化率")
        else:
            core_issue = "自然转化能力弱，高度依赖付费买量"
            evidence.append(f"{ad_ratio:.0f}%流量靠付费买 + 搜索转化率仅{conv_str}% → 自然搜索转化不行，停投就断流")
            priorities.append("先提升搜索转化率：优化标题关键词匹配、详情页卖点承接、评价维护")
    
    # ========== 流量承接OK + 重度付费 + 转化还行/好 ==========
    elif not tpm_bad and ad_heavy:
        if search_conv_good and roi_healthy:
            core_issue = "付费占比高，但自然转化基础好，有降付费空间"
            evidence.append(
                f"{ad_ratio:.0f}%付费 + 搜索转化率{conv_str}%"
                f"+ ROI {surface_roi:.2f} → 各项指标都不差，只是付费占比偏高，可以逐步调结构"
            )
            priorities.append("逐步降低付费占比，把预算投到搜索权重提升上，让自然流量接棒")
        elif search_conv_good and roi_mid:
            core_issue = "自然转化基础还行，但推广ROI拖了后腿"
            _sc_uv = result.get('_uv_value', {})
            _sc_lr = _sc_uv.get('launch', {}).get('roi') if isinstance(_sc_uv, dict) else None
            _sc_hr = _sc_uv.get('harvest', {}).get('roi') if isinstance(_sc_uv, dict) else None
            _sc_note = "推广结构健康，继续优化细节" if (_sc_lr is not None and _sc_hr is not None and _sc_lr >= 1.5 and _sc_hr >= 1.5) else "推广结构有优化空间"
            evidence.append(
                f"{ad_ratio:.0f}%付费 + 搜索转化率{conv_str}%"
                f"+ ROI {surface_roi:.2f} → 转化没问题，{_sc_note}"
            )
            priorities.append("优化推广结构：砍低效计划、加量高蓄水计划")
            priorities.append("逐步把预算从付费转向搜索权重，降低付费依赖")
        else:
            core_issue = "付费流量占比高，转化能力待提升"
            evidence.append(f"{ad_ratio:.0f}%流量靠付费买，搜索转化率{conv_str}% → 有降付费的基础，关键是把省下的预算投到搜索权重上")
            priorities.append("逐步降低付费占比，把预算投到搜索权重提升上，让自然流量接棒")
    
    # ========== 流量承接OK + 付费偏高（40-70%）==========
    elif ad_high and not core_issue:
        if search_conv_weak:
            core_issue = "搜索转化偏弱，页面承接是核心问题"
            evidence.append(
                f"付费占比{ad_ratio:.0f}% + 搜索转化率仅{conv_str}% → "
                "搜索用户主动找过来都不买，说明页面没说服用户下单"
            )
            priorities.append("优先修复详情页：首屏3秒能否让用户确认“这就是我想要的”")
            priorities.append("同步提升搜索转化率，降低对付费的依赖")
        else:
            core_issue = "付费占比偏高，但转化基础尚可"
            evidence.append(f"付费占比{ad_ratio:.0f}%，搜索转化率{conv_str}% → 推广结构需优化，但不紧急")
            priorities.append("逐步优化付费结构，向自然流量倾斜")
    
    # ========== 纯ROI亏损（无匹配/付费极端问题）==========
    elif roi_losing and not core_issue:
        core_issue = "推广ROI堪忧，先止血"
        evidence.append(f"ROI仅{surface_roi:.2f}，推广费花得多赚得少")
        priorities.append("先砍掉ROI为负的计划止损，再调整推广结构")
    
    # ========== 月销不足 ==========
    monthly_sales = result.get('monthly_sales')
    if monthly_sales and int(monthly_sales) < 100 and not core_issue:
        core_issue = "销量基数太小，自然流量飞轮没转起来"
    
    # ---- 补充证据（不改变核心矛盾，只追加上下文） ----
    
    # 退款率加重说明（核心矛盾已由四维度决定，退款率只补充影响）
    if refund_crisis and core_issue:
        if "推广" in core_issue or "亏损" in core_issue or "亏" in core_issue:
            evidence.append(f"退款率{refund_rate:.1f}%偏高（含平台凑单因素，仅供参考）")
        elif "脱节" in core_issue or "承接" in core_issue or "匹配" in core_issue:
            evidence.append(f"退款率{refund_rate:.1f}%偏高（含平台凑单因素，仅供参考）")
        elif "转化" in core_issue:
            evidence.append(f"退款率{refund_rate:.1f}%偏高（含平台凑单因素，仅供参考）")
        else:
            evidence.append(f"退款率{refund_rate:.1f}%偏高（含平台凑单因素，仅供参考）")
    elif refund_warning and core_issue:
        if not any(f"退款率{refund_rate:.1f}%" in e for e in evidence):
            evidence.append(f"退款率{refund_rate:.1f}%偏高（含平台满减凑单因素，仅供参考）")
    
    # 付费占比高的补充说明
    if ad_heavy:
        conv_hint = ""
        if search_conv_weak:
            conv_hint = f"，搜索转化率仅{conv_str}%远低于同行"
        elif natural_conv is not None and natural_conv < 3:
            conv_hint = f"，搜索转化率{conv_str}%低于同行均值"
        
        if not any(f"{ad_ratio:.0f}%流量靠付费买" in e for e in evidence):
            if refund_crisis:
                evidence.append(f"{ad_ratio:.0f}%流量靠付费买{conv_hint}")
            else:
                evidence.append(f"{ad_ratio:.0f}%流量靠付费买{conv_hint}")
        
        if not any("降低付费依赖" in p or "搜索权重" in p for p in priorities):            priorities.append("解决核心问题后，逐步把省下的预算投到搜索权重提升上，降低付费依赖")
    
    # 推广效率判断
    if surface_roi is not None:
        if roi_healthy:
            if tpm_bad:
                if not any("核心问题不在推广" in e for e in evidence):
                    evidence.append(f"ROI {surface_roi:.2f}，推广ROI没问题 → 核心问题不在推广，在承接")
            elif refund_crisis:
                if not any("退款才是利润杀手" in e for e in evidence):
                    evidence.append(f"ROI {surface_roi:.2f}，推广能赚钱，但要逐步降低付费依赖")
            elif ad_heavy:
                if not any("推广能赚钱" in e for e in evidence):
                    evidence.append(f"ROI {surface_roi:.2f}，推广能赚钱（高毛利支撑）→ 流量精准度有提升空间，但非致命问题")
            else:
                if not any("推广能赚钱" in e for e in evidence):
                    evidence.append(f"ROI {surface_roi:.2f}，推广能赚钱（高毛利支撑）→ 流量精准度有提升空间，但非致命问题")
        elif roi_mid:
            if not any("推广效率" in e for e in evidence):
                # 根据分层ROI判断结构健康度
                _early_uv = result.get('_uv_value', {}) if result else {}
                _early_l_roi = _early_uv.get('launch', {}).get('roi')
                _early_h_roi = _early_uv.get('harvest', {}).get('roi')
                if _early_l_roi is not None and _early_h_roi is not None and _early_l_roi >= 3.0 and _early_h_roi >= 4.0:
                    evidence.append(f"ROI {surface_roi:.2f}，推广能赚钱 → 保持当前结构，继续优化细节")
                else:
                    evidence.append(f"ROI {surface_roi:.2f}，推广ROI中等 → 结构有优化空间，但不是最紧急的")
        else:
            if not core_issue:
                core_issue = "推广ROI堪忧，先止血"
            if not any(f"ROI仅{surface_roi:.2f}" in e for e in evidence):
                evidence.append(f"ROI仅{surface_roi:.2f}，推广费花得多赚得少")
            if not any("砍掉" in p or "止损" in p for p in priorities):
                priorities.insert(0, "先砍掉ROI为负的计划止损，再调整推广结构" if surface_roi < 1.0 else "先优化ROI偏低的计划，再调整推广结构")
    
    # 蓄水亮点
    if best_cart_plan_name and best_cart_rate > 5:
        evidence.append(f"蓄水亮点：{best_cart_plan_name}加购率{best_cart_rate:.1f}%（蓄水=花钱换收藏加购），可以加量")
    
    # ---- 计算浪费金额（从低效计划聚合） ----
    # ---- 计算浪费金额（从低效计划聚合） ----
    # ---- 计算浪费金额（从低效计划聚合） ----
    waste_amount = 0
    waste_plan_count = 0
    if ad_diagnosis:
        # 拉新层低效计划
        worst_plans = ad_diagnosis.get('launch_diagnosis', {}).get('worst_plans', [])
        for p in worst_plans:
            # 排除最佳蓄水计划（它已被标为"加量"，不应同时算作低效浪费）
            if best_cart_plan_name and p.get('name', '') == best_cart_plan_name:
                continue
            cost = p.get('cost', 0) or 0
            waste_amount += cost
            waste_plan_count += 1
        # 收割层低效/浪费计划
        harvest_diag = ad_diagnosis.get('harvest_diagnosis', {})
        for p in harvest_diag.get('waste_plans', []):
            cost = p.get('cost', 0) or 0
            waste_amount += cost
            waste_plan_count += 1
        for p in harvest_diag.get('weak_plans', []):
            cost = p.get('cost', 0) or 0
            waste_amount += cost * 0.3  # 弱势计划按30%算浪费
            waste_plan_count += 1
    

    # ---- P2对齐：当流量结构诊断判定"推广依赖度过高"时，覆盖核心矛盾 ----
    _bottleneck_early = result.get('bottleneck_analysis', {})
    if _bottleneck_early and _bottleneck_early.get('bottleneck_channel') == '推广依赖度过高':
        # ad_data_card is a list, get ad_ratio from evidence or default
        _ad_ratio_p2 = 89  # default fallback
        _evidence_list = result.get("bottleneck_analysis", {}).get("evidence_chain", [])
        for _e in _evidence_list:
            _idx = _e.find("广告流量占比")
            if _idx >= 0:
                _rest = _e[_idx + 6:]  # after "广告流量占比"
                _digits = ""
                for _ch in _rest:
                    if _ch.isdigit():
                        _digits += _ch
                    else:
                        break
                if _digits:
                    _ad_ratio_p2 = int(_digits)
                    break
        core_issue = f"推广占比{_ad_ratio_p2:.0f}%导致流量精准性不足"
        evidence = list(_bottleneck_early.get('evidence_chain', []))
        priorities = []
        _p2_action_title = _bottleneck_early.get('action_title', '对比成交人群与推广人群标签，收缩人群包精准度')
        priorities.append(f"先排查人群精准度：{_p2_action_title}；同时暂停拉新ROI最低的推广计划止损")
        priorities.append("中期目标：提升自然搜索流量占比，降低对付费流量的依赖")
        priorities.append("收缩关键词匹配范围，减少广泛匹配，增加精确匹配占比")

    # ---- 组装30秒速览数据 ----
    # 关键数字
    metrics = []
    if waste_amount > 0:
        metrics.append({"icon": "💰", "label": "每月可优化资金", "value": f"¥{waste_amount:,.0f}", "sub": f"{waste_plan_count}个低效计划"})
    if surface_roi is not None:
        roi_color = "#c62828" if surface_roi < 2 else "#e65100" if surface_roi < 3 else "#2e7d32"
        roi_label = "拉新ROI偏低" if surface_roi < 2 else "ROI中等" if surface_roi < 3 else "ROI健康"
        metrics.append({"icon": "📊", "label": "推广ROI", "value": f"{surface_roi:.2f}", "sub": roi_label})
    if ad_ratio and ad_ratio > 70:
        metrics.append({"icon": "🔄", "label": "广告流量占比", "value": f"{ad_ratio:.0f}%", "sub": "付费依赖偏高"})
    elif ad_ratio:
        metrics.append({"icon": "🔄", "label": "广告流量占比", "value": f"{ad_ratio:.0f}%", "sub": "流量结构"})

    # 明天第一件事：取最urgent的动作，或important中省钱最多的
    _raw_for_tomorrow = (result.get('actions') or []) + (result.get('ad_actions') or [])
    _seen_tm = set()
    _unique_actions = []
    for a in _raw_for_tomorrow:
        t = a.get('title', '')
        if t and t not in _seen_tm:
            _seen_tm.add(t)
            _unique_actions.append(a)

    tomorrow_action = None
    _has_plan_kw = lambda a: any(kw in a.get('title','') for kw in ['日预算','计划','日均','直通车','引力魔方'])
    _plan_acts = [a for a in _unique_actions if _has_plan_kw(a)]
    _tm_cands = _plan_acts if _plan_acts else _unique_actions
    for a in _tm_cands:
        if a.get('priority') == 'urgent':
            tomorrow_action = a
            break
    if not tomorrow_action:
        top_savings = 0
        for a in _tm_cands:
            if a.get('priority') in ('important','urgent'):
                import re as _re
                exp = a.get('expected', '')
                m = _re.search(r'[¥￥]([\d,]+)', exp)
                if m:
                    s = int(m.group(1).replace(',', ''))
                    if s > top_savings:
                        top_savings = s
                        tomorrow_action = a
        _plan=[a for a in _unique_actions if any(k in a.get(chr(116)+chr(105)+chr(116)+chr(108)+chr(101),chr(32)) for k in [chr(20943),chr(30739),chr(21152),chr(26085)])];_c=_plan if _plan else _unique_actions
        if not tomorrow_action and _c:
            tomorrow_action = _c[0]

    # ---- 渲染30秒速览 ----
    speed_lines = []
    speed_lines.append('<div style="padding:1.5rem;background:linear-gradient(135deg,#0d1b2a 0%,#1b2838 100%);border-radius:16px;margin:0.5rem 0 1rem;color:#fff;">')
    speed_lines.append('<div style="font-size:0.8rem;color:#8899aa;letter-spacing:2px;margin-bottom:0.8rem;">⚡ 30秒速览</div>')

    # 核心矛盾
    if core_issue:
        speed_lines.append(f'<div style="font-size:1.3rem;font-weight:700;margin-bottom:0.3rem;line-height:1.4;">{core_issue}</div>')
        if evidence:
            brief = evidence[0] if len(evidence) == 1 else evidence[0] + "；" + evidence[1]
            speed_lines.append(f'<div style="font-size:0.9rem;color:#99aabb;margin-bottom:1rem;">{brief}</div>')

    # 关键数字卡片
    if metrics:
        speed_lines.append('<div style="display:flex;gap:0.8rem;flex-wrap:wrap;margin-bottom:1rem;">')
        for m in metrics:
            speed_lines.append(f'<div style="flex:1;min-width:100px;background:rgba(255,255,255,0.08);border-radius:10px;padding:0.8rem 1rem;text-align:center;">')
            speed_lines.append(f'<div style="font-size:0.75rem;color:#8899aa;">{m["icon"]} {m["label"]}</div>')
            speed_lines.append(f'<div style="font-size:1.5rem;font-weight:700;margin:0.2rem 0;">{m["value"]}</div>')
            speed_lines.append(f'<div style="font-size:0.8rem;color:#99aabb;">{m["sub"]}</div>')
            speed_lines.append('</div>')
        speed_lines.append('</div>')

    # 明天第一件事
    if tomorrow_action:
        tm_title = tomorrow_action.get('title', '')
        tm_what = tomorrow_action.get('what', '')
        tm_expected = tomorrow_action.get('expected', '')
        speed_lines.append('<div style="background:rgba(255,152,0,0.15);border-radius:10px;padding:0.8rem 1rem;border-left:3px solid #ff9800;">')
        speed_lines.append('<div style="font-size:0.75rem;color:#ff9800;font-weight:600;margin-bottom:0.3rem;">🎯 明天第一件事</div>')
        speed_lines.append(f'<div style="font-size:1rem;font-weight:600;margin-bottom:0.3rem;">{tm_title}</div>')
        speed_lines.append(f'<div style="font-size:0.85rem;color:#ccddee;">{tm_what}</div>')
        if tm_expected:
            speed_lines.append(f'<div style="font-size:0.85rem;color:#4caf50;margin-top:0.3rem;">📈 {tm_expected}</div>')
        speed_lines.append('</div>')

    speed_lines.append('</div>')
    st.markdown('\n'.join(speed_lines), unsafe_allow_html=True)

    # 详细分析折叠
    detail_parts = []
    _seen_ev=set()
    if evidence and len(evidence) > 0:
        _seen_ev.add(evidence[0].strip())
    for e in evidence[1:]:
        if e not in _seen_ev:
            _seen_ev.add(e)
            detail_parts.append(f"• {e}")
    if priorities:
        for i, p in enumerate(priorities, 1):
            detail_parts.append(f"{i}️⃣ {p}")
    if detail_parts:
        detail_html = '<br>'.join(detail_parts)
        with st.expander("📋 查看完整分析依据"):
            st.markdown(f'<div style="font-size:0.9rem;line-height:1.8;color:#555;">{detail_html}</div>', unsafe_allow_html=True)

    # ---- 一句话结论 ----
    one_liner = result.get('one_liner') or result.get('ad_one_liner', '')
    if one_liner:
        st.markdown(f'<div class="one-liner">📊 {one_liner}</div>', unsafe_allow_html=True)
    
        
    # ---- 因果归因诊断：流量结构瓶颈分析 ----
    bottleneck = result.get('bottleneck_analysis', {})
    if bottleneck and 'error' not in bottleneck and bottleneck.get('bottleneck_channel'):
        bn_channel = bottleneck.get('bottleneck_channel', '')
        bn_root = bottleneck.get('root_cause', '')
        bn_severity = bottleneck.get('severity', 'medium')
        bn_evidence = bottleneck.get('evidence_chain', [])
        bn_action = bottleneck.get('action', '')
        
        severity_colors = {'high': '#e53935', 'medium': '#fb8c00', 'low': '#43a047'}
        severity_labels = {'high': ' 高', 'medium': ' 中', 'low': ' 低'}
        sev_color = severity_colors.get(bn_severity, '#fb8c00')
        sev_label = severity_labels.get(bn_severity, ' 中')
        
        evidence_html = '<br>'.join([f'• {e}' for e in bn_evidence]) if bn_evidence else ''
        
        bn_html = f"""
        <div style="padding:1.2rem 1.5rem;background:linear-gradient(135deg,#f3e5f5 0%,#ede7f6 100%);border-radius:12px;margin:0.8rem 0 1rem;border-left:4px solid {sev_color};">
            <div style="font-size:0.85rem;color:#6a1b9a;font-weight:600;margin-bottom:0.5rem;"> 流量结构诊断 <span style="background:{sev_color};color:#fff;padding:2px 8px;border-radius:10px;font-size:0.75rem;margin-left:6px;">{sev_label}</span></div>
            <div style="font-size:1.05rem;font-weight:600;color:#1a1a2e;margin-bottom:0.4rem;">瓶颈定位：{bn_channel} → {bn_root}</div>
            <div style="font-size:0.88rem;color:#555;line-height:1.7;margin-bottom:0.5rem;">{evidence_html}</div>
            <div style="font-size:0.92rem;color:#1a1a2e;padding:0.6rem 0.8rem;background:rgba(255,255,255,0.7);border-radius:8px;">
                <b> 优先动作：</b>{bn_action}
            </div>
        </div>
        """
        st.markdown(bn_html, unsafe_allow_html=True)
    
    # ---- 优先动作（去重 + 数据关联校验） ----
    _raw_actions = (result.get('actions') or []) + (result.get('ad_actions') or [])
    _seen = set()
    all_actions = []
    for a in _raw_actions:
        t = a.get('title', '')
        if t not in _seen:
            _seen.add(t)
            # 数据关联校验：如果动作没有引用具体计划名/具体数据，且标记为urgent，降级为suggest
            what = a.get('what', '')
            why = a.get('why', '')
            if a.get('priority') == 'urgent' and a.get('type') != 'traffic_precision_fix':
                # 检查what是否有具体可执行指令（含具体金额/具体计划名）
                # 而非检查why——why中泛提指标名+偶然出现%会误判
                import re
                # 同时检查what和target（scoring_engine用target存计划名）
                _action_target = a.get('target', '')
                has_specific_data = any([
                    '¥' in what,                              # 具体预算金额
                    bool(re.search(r'_20\d{5,6}', what + _action_target)),  # what或target含日期后缀
                    bool(re.search(r'ROI\s*[\d.]+', why)),    # why含具体ROI数值
                ])
                if not has_specific_data:
                    a = dict(a)  # 复制避免修改原始数据
                    a['priority'] = 'suggest'
            all_actions.append(a)
    
    if all_actions:
        # 提取"本周最关键"动作：优先取urgent，其次取important中预期节省金额最大的
        top_action = None
        top_savings = 0
        urgent_actions = [a for a in all_actions if a.get('priority') == 'urgent']
        important_actions = [a for a in all_actions if a.get('priority') == 'important']
        
        if urgent_actions:
            top_action = urgent_actions[0]
        elif important_actions:
            import re
            for a in important_actions:
                exp = a.get('expected', '')
                # 从预期中提取节省金额
                m = re.search(r'¥([\d,]+)', exp)
                if m:
                    savings = int(m.group(1).replace(',', ''))
                    if savings > top_savings:
                        top_savings = savings
                        top_action = a
            if not top_action:
                top_action = important_actions[0]
        
        # ⭐ 本周最关键已整合进30秒速览区
        
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
    
# ---- P1: Category Self-Check List (causal diagnosis driven) ----
    _bn = result.get('bottleneck_analysis', {})
    _bn_ch = _bn.get('bottleneck_channel', '')
    _bn_sev = _bn.get('severity', '')

    _checklist = []
    if _bn_ch and _bn_sev in ('medium', 'high'):
        if _bn_ch == '搜索':
            _checklist = [
                ('详情页首屏3秒测试', '打开商品详情页，3秒内能否确认“这就是我想要的”？首屏是否清晰展示了品类核心卖点（如过滤效果、出水速度、安装便捷性）？'),
                ('价格竞争力对标', '搜索TOP10竞品中，你的价格处于什么位置？如果偏高，是否有足够的差异化卖点支撑？'),
                ('评价区负面信息排查', '打开评价区前20条，是否有高频负面关键词（如安装麻烦、漏水、噪音）？这些是否是用户下单顾虑？'),
                ('主图与搜索意图匹配', '用户搜的核心词和你的主图展示是否一致？如果搜“净水器家用”但主图强调“商用大流量”，点击后转化会低'),
                ('问大家/买家秀质量', '问大家前5个问题是否涉及用户核心顾虑？买家秀是否真实展示了使用场景？'),
            ]
        elif _bn_ch == '购物车':
            _checklist = [
                ('确认产品复购属性', '这个品类是否有复购需求？如净水器滤芯需要定期更换，属于复购品类；如果是一次性品类则购物车占比低是正常的'),
                ('老客召回机制检查', '是否开通了短信/优惠券/会员体系召回老客？在客户运营平台查看“老客召回”相关工具是否启用'),
                ('复购周期提醒设置', '对于复购品类（如滤芯），是否根据使用周期设置了自动提醒？如“距上次购买已90天，该换滤芯了”'),
                ('售后触达覆盖', '签收后是否有好评引导、使用教程推送、售后关怀等动作？这些是建立复购信任的基础'),
                ('会员/店铺关注激励', '是否有关注店铺送优惠券、会员积分体系等机制，让用户有理由回来看一眼？'),
            ]

    if _checklist:
        _cl_title = '详情页自查清单' if _bn_ch == '搜索' else '复购链路自查清单'
        _cl_items = ''
        for _j, (_cl_item, _cl_desc) in enumerate(_checklist, 1):
            _cl_items += f"""
            <div style="padding:0.6rem 0.8rem;margin:0.3rem 0;background:rgba(255,255,255,0.8);border-radius:6px;border-left:3px solid #7b1fa2;">
                <div style="font-weight:600;color:#4a148c;font-size:0.9rem;">{_j}. {_cl_item}</div>
                <div style="color:#555;font-size:0.85rem;margin-top:0.2rem;">{_cl_desc}</div>
            </div>"""

        _cl_html = f"""
        <div style="padding:1.2rem 1.5rem;background:linear-gradient(135deg,#f3e5f5 0%,#ede7f6 100%);border-radius:12px;margin:0.8rem 0 1rem;border-left:4px solid #7b1fa2;">
            <div style="font-size:0.85rem;color:#6a1b9a;font-weight:600;margin-bottom:0.5rem;">📋 {_cl_title}（{len(_checklist)}项）</div>
            <div style="font-size:0.88rem;color:#555;margin-bottom:0.6rem;">诊断定位瓶颈在<b>{_bn_ch}</b>，对照以下清单逐项排查：</div>
            {_cl_items}
        </div>
        """
        st.markdown(_cl_html, unsafe_allow_html=True)
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
        
        # 首次出现术语内联解释
        inline_hints = {
            '搜索转化率': '搜索转化率（用户搜到你的商品后下单的比例）',
            '广告转化率': '广告转化率（点击广告后下单的比例）',
            '跳失率': '跳失率（进来什么都没看就走掉的比例）',
            '广告流量占比': '广告流量占比（付费流量占总流量的比例）',
        }
        
        for line in data_card:
            if '链接质量' in line or '链接质量指标' in line:
                current_section = 'quality'
                continue
            elif '生意指标' in line:
                current_section = 'business'
                continue
            elif line == '---':
                continue
            # 术语内联：首次出现时加简短解释
            for term, hint in inline_hints.items():
                if term in line and hint not in line:
                    line = line.replace(term, hint, 1)
                    # 只替换第一次出现，后续不再加解释
                    inline_hints[term] = term
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
    
    # ---- 人货匹配深度分析 ----
    match_analysis = analyze_visitor_product_match(result, ad_diagnosis)
    if match_analysis.get('match_verdict') or match_analysis.get('improvements'):
        st.markdown("##### 🧲 人货匹配深度分析")
        
        vp = match_analysis.get('visitor_profile', {})
        if vp:
            visitor_html = f"**访客画像**：{vp.get('user_type', '')}（{vp.get('dominant_channel', '')}占比{vp.get('dominant_ratio', '')}）"
            st.markdown(f'<div class="data-card">{visitor_html}</div>', unsafe_allow_html=True)
        
        # 定向类型花费分布
        plan_types = match_analysis.get('plan_types', {})
        if plan_types:
            total_ad = sum(plan_types.values())
            type_parts = []
            for t, cost in sorted(plan_types.items(), key=lambda x: -x[1]):
                pct = cost / total_ad * 100 if total_ad > 0 else 0
                type_parts.append(f"{t} ¥{cost:,.0f}（{pct:.0f}%）")
            st.markdown(f'<div class="data-card">**广告定向分布**：{" | ".join(type_parts)}</div>', unsafe_allow_html=True)
        
        # 匹配度判断
        verdict = match_analysis.get('match_verdict', '')
        if verdict:
            st.markdown(f'<div style="padding:0.8rem 1rem;background:#fff3e0;border-radius:8px;margin:0.3rem 0;font-size:0.95rem;">🎯 {verdict}</div>', unsafe_allow_html=True)
        
        # 品类卖点覆盖
        covered = match_analysis.get('covered_selling_points', [])
        uncovered = match_analysis.get('uncovered_selling_points', [])
        if covered or uncovered:
            cov_str = '、'.join(covered) if covered else '无'
            uncov_str = '、'.join(uncovered) if uncovered else '无'
            _dbg_title = match_analysis.get('_debug_product_title', 'N/A')
            _dbg_plans = match_analysis.get('_debug_plan_names', 'N/A')
            st.markdown(f'<div class="data-card">**品类核心卖点覆盖**：✅ 已覆盖：{cov_str} | ❌ 未覆盖：{uncov_str}<br><span style="font-size:0.8em;color:#999;">商品标题：{_dbg_title} | 搜索范围计划：{_dbg_plans}</span></div>', unsafe_allow_html=True)
        
        # 改进建议
        improvements = match_analysis.get('improvements', [])
        if improvements:
            for imp in improvements:
                st.markdown(f'<div class="data-card">💡 {imp}</div>', unsafe_allow_html=True)
        
        # 升级路径提示
        st.markdown('<div style="font-size:0.8rem;color:#999;margin-top:0.5rem;">📌 当前分析基于广告投放策略和品类卖点清单推断。如需更精准的访客画像×页面风格对齐分析，请补充：访客画像数据（生意参谋→市场→访客分析）、搜索关键词TOP20、退款原因分布</div>', unsafe_allow_html=True)
    
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
            refund_rate_float = float(refund_rate)
            if refund_rate_float > 40:
                risk_label = "偏高"
            elif refund_rate_float > 30:
                risk_label = "偏高"
            else:
                risk_label = "正常"
            if risk_label != "正常":
                cause_text = {
                    'hybrid_plan_cart_stuffing': '全站推广凑单导致',
                    'traffic_imprecision': '流量不精准导致',
                }.get(refund_cause, '需退款明细数据排查原因')
                st.metric("退款风险", f"{risk_label} — {cause_text}")
            else:
                st.metric("退款风险", "正常")
        
        # 跨模块关联分析：退款率 × 流量承接效率
        if float(refund_rate) > 30:
            tpm = dims.get('traffic_page_match', {}).get('score')
            if tpm is not None and tpm < 5:
                st.warning(f"⚠️ 退款率{float(refund_rate):.1f}% + {eff_brief} → "
                    "天猫平台满减凑单现象普遍，未发货退款占比高时多为凑单行为，不代表链接质量问题。"
                    "建议导出退款原因明细区分凑单退款和质量退款。")
                st.caption("📌 退款率含平台满减凑单因素，建议导出退款原因分布数据进一步分析。")
                pass  # caption replaced above
            elif float(refund_rate) > 30:
                st.warning(f"⚠️ 退款率{float(refund_rate):.1f}%偏高（含平台满减凑单因素），建议导出退款原因明细区分凑单和质量退款。")
                st.caption("📌 天猫平台满减凑单导致高退款率是普遍现象，需结合退款原因分布判断。")
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
                st.metric("ROI", f"{surface_roi:.2f}")
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
                st.markdown(f"花费 ¥{launch['total_cost']:,.0f}，ROI {launch.get('surface_roi', '?')}")
            best = launch.get('best_cart_plan')
            if best:
                st.markdown(f"**最佳蓄水**：{best.get('plan_name', '—')}")
                lc1, lc2, lc3 = st.columns(3)
                with lc1:
                    st.metric("加购率", f"{best.get('cart_rate', 0):.1f}%")
                with lc2:
                    st.metric("收藏加购成本", f"¥{best.get('fav_cart_cost', 0):.1f}")
                with lc3:
                    st.metric("ROI", f"{best.get('surface_roi', 0):.2f}")
        # ---- UV价值对比（替代流量承接效率评分） ----
        uv_info = result.get('_uv_value', {})
        if uv_info and (uv_info.get('launch', {}).get('uv_value') is not None or uv_info.get('harvest', {}).get('uv_value') is not None):
            st.markdown("#### \U0001f4ca UV价值对比")
            st.caption("每花1块钱买来的流量，能赚回多少价值？UV价值 > 点击成本x2 = 赚钱（按50%毛利计）")

            l_uv = uv_info.get('launch', {})
            h_uv = uv_info.get('harvest', {})

            if l_uv.get('uv_value') is not None:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("拉新UV价值", f"\u00a5{l_uv['uv_value']:.2f}", help="直接成交价值 + 蓄水价值")
                with col2:
                    parts = [f"直接\u00a5{l_uv.get('direct_value', 0):.2f}"]
                    if l_uv.get('water_value'):
                        parts.append(f"蓄水\u00a5{l_uv['water_value']:.2f}")
                    st.metric("价值构成", " + ".join(parts), help="蓄水价值为预估值（基于加购率×回店率×客单价推算）")
                    # 短期/长期分拆提示
                    _dv = l_uv.get('direct_value', 0) or 0
                    _cpc = l_uv.get('cpc', 0) or 0
                    if _dv < _cpc and l_uv.get('water_value', 0) > 0:
                        st.caption(f"直接成交¥{_dv:.2f} < CPC¥{_cpc:.2f}，当次微亏；蓄水¥{l_uv['water_value']:.2f}表明长期价值健康")
                with col3:
                    st.metric("点击成本CPC", f"\u00a5{l_uv.get('cpc', 0):.2f}")
                with col4:
                    l_roi = l_uv.get('roi', 0)
                    if l_roi:
                        roi_emoji = "\U0001f7e2" if l_roi >= 3.0 else ("\U0001f7e1" if l_roi >= 2.0 else "\U0001f534")
                        st.metric("ROI", f"{roi_emoji} {l_roi:.2f}")
                    else:
                        st.metric("ROI", "\u2014")

                ret_rate = uv_info.get('return_rate')
                ret_rate_display = uv_info.get('return_rate_display', ret_rate)
                if ret_rate is not None:
                    cfv = uv_info.get("cart_fav_visitors", "?")
                    tc = uv_info.get("total_cart", "?")
                    st.caption(f"回店率{ret_rate_display:.1%}（购物车渠道访客{cfv}÷加购人数{tc}），客单价¥{uv_info.get('avg_price', 0):.0f}")

            if h_uv.get('uv_value') is not None:
                hc1, hc2, hc3 = st.columns(3)
                with hc1:
                    st.metric("收割UV价值", f"\u00a5{h_uv['uv_value']:.2f}")
                with hc2:
                    st.metric("点击成本CPC", f"\u00a5{h_uv.get('cpc', 0):.2f}")
                with hc3:
                    h_roi = h_uv.get('roi', 0)
                    if h_roi:
                        roi_emoji = "\U0001f7e2" if h_roi >= 4.0 else ("\U0001f7e1" if h_roi >= 3.0 else "\U0001f534")
                        st.metric("ROI", f"{roi_emoji} {h_roi:.2f}")
                    else:
                        st.metric("ROI", "\u2014")

        
        # 收割层（拆到具体计划）
        harvest = ad_diagnosis.get('harvest_diagnosis', {})
        if harvest:
            total_cost = harvest.get('total_cost', 0)
            if total_cost and total_cost > 0:
                st.markdown("#### 🟠 收割层")
                st.markdown(f"花费 ¥{total_cost:,.0f}，ROI {harvest.get('surface_roi', '?')}")
                
                # 合格计划
                qualified = harvest.get('qualified_plans', [])
                if qualified:
                    st.markdown('<div style="font-size:0.85rem;color:#2e7d32;font-weight:600;margin:0.5rem 0 0.3rem;">✅ 高效收割</div>', unsafe_allow_html=True)
                    for p in qualified:
                        name = p.get('plan_name', '—')
                        cost = p.get('cost', 0) or 0
                        roi = p.get('surface_roi', 0) or 0
                        conv = p.get('conv_rate', 0) or 0
                        st.markdown(f'<div class="data-card"><b>{name}</b> — 花费¥{cost:,.0f}，ROI {roi:.2f}，转化率{conv:.2f}%</div>', unsafe_allow_html=True)
                
                # 弱势计划
                weak = harvest.get('weak_plans', [])
                if weak:
                    st.markdown('<div style="font-size:0.85rem;color:#e65100;font-weight:600;margin:0.5rem 0 0.3rem;">⚠️ 效率偏低</div>', unsafe_allow_html=True)
                    for p in weak:
                        name = p.get('plan_name', '—')
                        cost = p.get('cost', 0) or 0
                        roi = p.get('surface_roi', 0) or 0
                        conv = p.get('conv_rate', 0) or 0
                        note = p.get('new_cust_note', '')
                        st.markdown(f'<div class="data-card"><b>{name}</b> — 花费¥{cost:,.0f}，ROI {roi:.2f}，转化率{conv:.2f}%{"（" + note + "）" if note else ""}</div>', unsafe_allow_html=True)
                
                # 浪费计划
                waste = harvest.get('waste_plans', [])
                if waste:
                    st.markdown('<div style="font-size:0.85rem;color:#c62828;font-weight:600;margin:0.5rem 0 0.3rem;">🔴 效率堪忧</div>', unsafe_allow_html=True)
                    for p in waste:
                        name = p.get('plan_name', '—')
                        cost = p.get('cost', 0) or 0
                        roi = p.get('surface_roi', 0) or 0
                        conv = p.get('conv_rate', 0) or 0
                        st.markdown(f'<div class="data-card"><b>{name}</b> — 花费¥{cost:,.0f}，ROI {roi:.2f}，转化率{conv:.2f}% — ROI<1.5，收割效率不达标，建议减预算或暂停</div>', unsafe_allow_html=True)
                
                # 没有分类数据时回退
                if not qualified and not weak and not waste:
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
                    st.metric("ROI", f"{(plan.get('surface_roi') or 0):.2f}")
                with hc3:
                    st.metric("转化率", f"{plan.get('conv_rate', 0):.2f}%")
    else:
        st.markdown("### 💰 推广诊断")
        st.info("未上传推广报表，无法进行推广深度分析。上传阿里妈妈计划报表可解锁ROI、蓄水效率等诊断。")
    
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

    # ---- 内测反馈入口 ----
    st.markdown("---")
    st.markdown('''
    <div style="background:linear-gradient(135deg,#f0f4ff 0%,#e8eeff 100%);border-radius:12px;padding:1.5rem;margin:1rem 0;border:1px solid #c3d5ff;">
        <div style="font-size:1rem;font-weight:600;color:#1a3a6e;margin-bottom:0.5rem;">📩 内测反馈</div>
        <div style="font-size:0.9rem;color:#445;line-height:1.6;">
            这是一个邀请制内测版本，感谢您的使用。如果诊断结果对您有帮助，或者您发现了任何问题，欢迎反馈：<br>
            • 微信：<strong>19121479116</strong><br>
            • 邮箱：<strong>345700101@qq.com</strong><br>
            <span style="color:#888;font-size:0.8rem;">您的反馈会帮助我们持续优化诊断质量</span>
        </div>
    </div>
    ''', unsafe_allow_html=True)


# ============================================================
# 主页面
# ============================================================

# Header
st.markdown('<div class="main-header">📊 电商链接诊断</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">看见数据背后的真相，做对每一个经营决策。</div>', unsafe_allow_html=True)

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
        <span class="step-badge">3</span> 诊断引擎18维度评分 + 推广深度分析
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
