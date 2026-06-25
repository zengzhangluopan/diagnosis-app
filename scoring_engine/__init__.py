"""
18维度全链路诊断 - 自动评分引擎
版本: V2.0
更新: 2026-05-26

V2.0 变更（基于真实数据踩坑）:
  1. 数据源标记：每个维度参数标记来源(real/semi/auto/missing)，报告里一目了然
  2. 广告稀释检测：当广告流量占比>70%时自动预警，强制使用分渠道数据
  3. 参数语义校验：promo_vs_daily_conv_ratio 只能填促销/日常转化比，
     不能填广告/自然转化比，填错直接拒绝

使用方式:
  from scoring_engine import DiagnosisEngine
  engine = DiagnosisEngine(raw_data={...})
  result = engine.run()
  engine.save_report(result, "./output/诊断报告.md")
"""

import json
import os
from datetime import datetime, date
from typing import Optional

# ============================================================
# 一、18维度评分函数
# 每个函数接收原始数据，返回 0-10 分
# ============================================================

def score_traffic_quality(
    precise_keyword_ratio: float,
    paid_keyword_quality_score: float,
    audience_overlap: float,
    # 推荐渠道
    recommend_audience_overlap: Optional[float] = None,
    recommend_fav_cart_rate: Optional[float] = None,
    # 内容/直播渠道
    content_audience_overlap: Optional[float] = None,
    content_bounce_rate: Optional[float] = None,
    # 加购收藏渠道
    cart_conv_rate: Optional[float] = None,
    fav_conv_rate: Optional[float] = None,
    # 流量占比
    search_traffic_ratio: float = 0.55,
    recommend_traffic_ratio: float = 0.20,
    content_traffic_ratio: float = 0.10,
    cart_fav_traffic_ratio: float = 0.15,
) -> dict:
    """流量质量精准度（权重13%）- 分渠道评估后加权"""
    
    # --- 搜索渠道评分 ---
    if precise_keyword_ratio >= 85 and paid_keyword_quality_score >= 8:
        search_score = 10
    elif precise_keyword_ratio >= 70 and paid_keyword_quality_score >= 7:
        search_score = 8 + (precise_keyword_ratio - 70) / 15 * 1
    elif precise_keyword_ratio >= 60 and paid_keyword_quality_score >= 7:
        search_score = 6 + (precise_keyword_ratio - 60) / 10 * 2
    elif precise_keyword_ratio >= 40:
        search_score = 4 + (precise_keyword_ratio - 40) / 20 * 2
    elif precise_keyword_ratio >= 20:
        search_score = 2 + (precise_keyword_ratio - 20) / 20 * 2
    else:
        search_score = precise_keyword_ratio / 20 * 2
    search_score = round(min(10, max(0, search_score)), 1)
    
    # --- 推荐渠道评分 ---
    if recommend_audience_overlap is not None and recommend_fav_cart_rate is not None:
        if recommend_audience_overlap >= 85 and recommend_fav_cart_rate >= 8:
            rec_score = 10
        elif recommend_audience_overlap >= 70:
            rec_score = 8 + (recommend_audience_overlap - 70) / 15 * 1
        elif recommend_audience_overlap >= 60:
            rec_score = 6 + (recommend_audience_overlap - 60) / 10 * 2
        elif recommend_audience_overlap >= 50:
            rec_score = 4 + (recommend_audience_overlap - 50) / 10 * 2
        elif recommend_audience_overlap >= 30:
            rec_score = 2 + (recommend_audience_overlap - 30) / 20 * 2
        else:
            rec_score = recommend_audience_overlap / 30 * 2
        rec_score = round(min(10, max(0, rec_score)), 1)
    else:
        rec_score = None
    
    # --- 内容/直播渠道评分 ---
    if content_audience_overlap is not None and content_bounce_rate is not None:
        if content_audience_overlap >= 85 and content_bounce_rate <= 20:
            content_score = 10
        elif content_audience_overlap >= 70 and content_bounce_rate <= 35:
            content_score = 8 + (content_audience_overlap - 70) / 15 * 1
        elif content_audience_overlap >= 60 and content_bounce_rate <= 50:
            content_score = 6 + (content_audience_overlap - 60) / 10 * 2
        elif content_audience_overlap >= 40 and content_bounce_rate <= 70:
            content_score = 4 + (content_audience_overlap - 40) / 20 * 2
        elif content_audience_overlap >= 20:
            content_score = 2 + (content_audience_overlap - 20) / 20 * 2
        else:
            content_score = content_audience_overlap / 20 * 2
        content_score = round(min(10, max(0, content_score)), 1)
    else:
        content_score = None
    
    # --- 加购收藏渠道评分 ---
    if cart_conv_rate is not None and fav_conv_rate is not None:
        if cart_conv_rate >= 35 and fav_conv_rate >= 20:
            cart_fav_score = 10
        elif cart_conv_rate >= 25:
            cart_fav_score = 8 + (cart_conv_rate - 25) / 10 * 1
        elif cart_conv_rate >= 15:
            cart_fav_score = 6 + (cart_conv_rate - 15) / 10 * 2
        elif cart_conv_rate >= 10:
            cart_fav_score = 4 + (cart_conv_rate - 10) / 5 * 2
        elif cart_conv_rate >= 5:
            cart_fav_score = 2 + (cart_conv_rate - 5) / 5 * 2
        else:
            cart_fav_score = cart_conv_rate / 5 * 2
        cart_fav_score = round(min(10, max(0, cart_fav_score)), 1)
    else:
        cart_fav_score = None
    
    # --- 加权综合 ---
    scores = {}
    weights = {}
    if True:  # 搜索必填
        scores['search'] = search_score
        weights['search'] = search_traffic_ratio
    if rec_score is not None:
        scores['recommend'] = rec_score
        weights['recommend'] = recommend_traffic_ratio
    if content_score is not None:
        scores['content'] = content_score
        weights['content'] = content_traffic_ratio
    if cart_fav_score is not None:
        scores['cart_fav'] = cart_fav_score
        weights['cart_fav'] = cart_fav_traffic_ratio
    
    # 归一化权重
    total_w = sum(weights.values())
    weighted_score = sum(scores[k] * weights[k] for k in scores) / total_w if total_w > 0 else 0
    weighted_score = round(min(10, max(0, weighted_score)), 1)
    
    return {
        'score': weighted_score,
        'channels': scores,
        'detail': {
            'precise_keyword_ratio': precise_keyword_ratio,
            'paid_keyword_quality_score': paid_keyword_quality_score,
            'audience_overlap': audience_overlap,
        }
    }


def score_traffic_page_match(
    precise_bounce_rate: float,
    top20_keyword_coverage: float,
    has_channel_landing_pages: bool = False,
    ad_traffic_ratio: float = 0,  # 广告流量占比（0-1）
    natural_bounce_rate: float = None,  # 自然搜索跳出率（分渠道数据，更精准）
) -> dict:
    """流量-页面匹配度（权重20%）
    
    V2.1改进：当广告流量占比>70%时，整体跳出率失真，需降权或用分渠道数据。
    原因：广告流量太泛导致整体跳出率虚高，不代表页面有问题。
    """
    
    # 判断跳出率指标是否失真
    bounce_distorted = ad_traffic_ratio > 0.70 and natural_bounce_rate is None
    
    # 选择有效的跳出率：有自然搜索跳出率就用，否则用整体
    effective_bounce_rate = natural_bounce_rate if natural_bounce_rate is not None else precise_bounce_rate
    
    # 跳失率评分（越低越好）
    if effective_bounce_rate <= 20:
        bounce_score = 10
    elif effective_bounce_rate <= 35:
        bounce_score = 8 + (35 - effective_bounce_rate) / 15 * 2
    elif effective_bounce_rate <= 50:
        bounce_score = 6 + (50 - effective_bounce_rate) / 15 * 2
    elif effective_bounce_rate <= 65:
        bounce_score = 4 + (65 - effective_bounce_rate) / 15 * 2
    elif effective_bounce_rate <= 80:
        bounce_score = 2 + (80 - effective_bounce_rate) / 15 * 2
    else:
        bounce_score = max(0, (100 - effective_bounce_rate) / 20 * 2)
    
    # 搜索词覆盖评分
    if top20_keyword_coverage >= 90:
        cover_score = 10
    elif top20_keyword_coverage >= 70:
        cover_score = 8 + (top20_keyword_coverage - 70) / 20 * 2
    elif top20_keyword_coverage >= 50:
        cover_score = 5 + (top20_keyword_coverage - 50) / 20 * 3
    elif top20_keyword_coverage >= 30:
        cover_score = 2 + (top20_keyword_coverage - 30) / 20 * 3
    else:
        cover_score = top20_keyword_coverage / 30 * 2
    
    # 落地页加分
    landing_bonus = 1.0 if has_channel_landing_pages else 0
    
    # 综合权重：跳出率失真时大幅降权（60%→20%），覆盖度和落地页升权
    if bounce_distorted:
        score = bounce_score * 0.20 + cover_score * 0.55 + (landing_bonus * 10) * 0.25
    else:
        score = bounce_score * 0.6 + cover_score * 0.3 + (landing_bonus * 10) * 0.1
    score = round(min(10, max(0, score)), 1)
    
    result = {
        'score': score,
        'detail': {
            'precise_bounce_rate': precise_bounce_rate,
            'top20_keyword_coverage': top20_keyword_coverage,
            'has_channel_landing_pages': has_channel_landing_pages,
            'ad_traffic_ratio': ad_traffic_ratio,
            'bounce_distorted': bounce_distorted,
        }
    }
    if natural_bounce_rate is not None:
        result['detail']['natural_bounce_rate'] = natural_bounce_rate
    
    return result


def score_position_rank(
    core_keyword_rank_page: float,
    natural_traffic_ratio: float,
) -> dict:
    """位置排名（权重3%）"""
    if core_keyword_rank_page <= 1:
        rank_score = 10
    elif core_keyword_rank_page <= 2:
        rank_score = 8 + (2 - core_keyword_rank_page) * 2
    elif core_keyword_rank_page <= 5:
        rank_score = 5 + (5 - core_keyword_rank_page) / 3 * 3
    elif core_keyword_rank_page <= 10:
        rank_score = 2 + (10 - core_keyword_rank_page) / 5 * 3
    else:
        rank_score = max(0, 2 - (core_keyword_rank_page - 10) / 10 * 2)
    
    if natural_traffic_ratio >= 85:
        nat_score = 10
    elif natural_traffic_ratio >= 70:
        nat_score = 8 + (natural_traffic_ratio - 70) / 15 * 2
    elif natural_traffic_ratio >= 50:
        nat_score = 6 + (natural_traffic_ratio - 50) / 20 * 2
    elif natural_traffic_ratio >= 30:
        nat_score = 4 + (natural_traffic_ratio - 30) / 20 * 2
    elif natural_traffic_ratio >= 10:
        nat_score = 2 + (natural_traffic_ratio - 10) / 20 * 2
    else:
        nat_score = natural_traffic_ratio / 10 * 2
    
    score = rank_score * 0.6 + nat_score * 0.4
    score = round(min(10, max(0, score)), 1)
    
    return {
        'score': score,
        'detail': {
            'core_keyword_rank_page': core_keyword_rank_page,
            'natural_traffic_ratio': natural_traffic_ratio,
        }
    }


def score_time_node(
    current_date_str: str,
    industry_search_trend: int = 3,  # 1=持续下滑 2=偏低 3=稳定 4=上升 5=暴增
) -> dict:
    """时间节点（权重3%）- 根据日期和大促日历自动判断"""
    
    # 大促日历（2026年）
    promo_calendar = {
        '03-08': ('妇女节', 0.5),
        '05-20': ('520', 0.8),
        '06-01': ('618预热', 1.0),
        '06-16': ('618正式', 2.0),
        '06-18': ('618爆发', 2.5),
        '08-08': ('88会员节', 0.8),
        '09-09': ('99大促', 1.0),
        '10-20': ('双11预热', 1.2),
        '11-01': ('双11开门红', 1.5),
        '11-11': ('双11爆发', 2.5),
        '12-12': ('双12', 1.0),
        '12-25': ('圣诞', 0.5),
    }
    
    try:
        today = datetime.strptime(current_date_str, '%Y-%m-%d').date()
    except:
        today = date.today()
    
    # 计算距最近大促的天数和加成
    min_days = 999
    promo_boost = 0
    year = today.year
    
    for date_str, (name, boost) in promo_calendar.items():
        promo_date = date(year, int(date_str.split('-')[0]), int(date_str.split('-')[1]))
        days = (promo_date - today).days
        if 0 <= days <= 14:  # 14天内有大促
            if days <= 3:
                promo_boost = max(promo_boost, boost * 2)  # 正式期加倍
            elif days <= 7:
                promo_boost = max(promo_boost, boost * 1.5)  # 预热期
            else:
                promo_boost = max(promo_boost, boost)  # 准备期
        if abs(days) < min_days:
            min_days = abs(days)
    
    # 季节性（按月）
    month = today.month
    # 通用电商旺季：6月/11月/12月，淡季：2月/7月
    season_map = {1: 3, 2: 2, 3: 3, 4: 3, 5: 4, 6: 5, 7: 2, 8: 3, 9: 4, 10: 4, 11: 5, 12: 5}
    season_score = season_map.get(month, 3)
    
    # 综合
    base_score = season_score * 0.4 + industry_search_trend * 0.4 + min(promo_boost, 5) * 0.4
    score = round(min(10, max(0, base_score)), 1)
    
    return {
        'score': score,
        'detail': {
            'current_date': current_date_str,
            'season_score': season_score,
            'promo_boost': round(promo_boost, 1),
            'search_trend': industry_search_trend,
        }
    }


def score_main_image_ctr(
    main_image_ctr: float,
    industry_avg_ctr: float,
) -> dict:
    """主图点击率（权重5%）"""
    ratio = main_image_ctr / industry_avg_ctr if industry_avg_ctr > 0 else 0
    
    if ratio >= 1.5:
        score = 10
    elif ratio >= 1.2:
        score = 8 + (ratio - 1.2) / 0.3 * 2
    elif ratio >= 0.9:
        score = 6 + (ratio - 0.9) / 0.3 * 2
    elif ratio >= 0.7:
        score = 4 + (ratio - 0.7) / 0.2 * 2
    elif ratio >= 0.5:
        score = 2 + (ratio - 0.5) / 0.2 * 2
    else:
        score = max(0, ratio / 0.5 * 2)
    
    return {
        'score': round(score, 1),
        'detail': {
            'main_image_ctr': main_image_ctr,
            'industry_avg_ctr': industry_avg_ctr,
            'ratio_to_industry': round(ratio, 2),
        }
    }


def score_detail_page_logic(
    first_3_screen_stay_ratio: float,
    page_read_completion: float,
    logic_completeness: int = 3,  # 1-5 人工补充
) -> dict:
    """详情页五层逻辑（权重4%）- 半自动"""
    
    if first_3_screen_stay_ratio >= 70:
        stay_score = 10
    elif first_3_screen_stay_ratio >= 50:
        stay_score = 6 + (first_3_screen_stay_ratio - 50) / 20 * 4
    elif first_3_screen_stay_ratio >= 30:
        stay_score = 3 + (first_3_screen_stay_ratio - 30) / 20 * 3
    else:
        stay_score = first_3_screen_stay_ratio / 30 * 3
    
    if page_read_completion >= 40:
        read_score = 10
    elif page_read_completion >= 25:
        read_score = 7 + (page_read_completion - 25) / 15 * 3
    elif page_read_completion >= 15:
        read_score = 4 + (page_read_completion - 15) / 10 * 3
    else:
        read_score = page_read_completion / 15 * 4
    
    logic_score = logic_completeness * 2  # 1-5 → 2-10
    
    score = stay_score * 0.35 + read_score * 0.35 + logic_score * 0.3
    score = round(min(10, max(0, score)), 1)
    
    return {
        'score': score,
        'detail': {
            'first_3_screen_stay_ratio': first_3_screen_stay_ratio,
            'page_read_completion': page_read_completion,
            'logic_completeness_manual': logic_completeness,
        }
    }


def score_review_quality(
    good_review_rate: float,
    image_review_ratio: float,
    core_complaint_ratio: float = 0,  # 核心卖点相关差评占比
) -> dict:
    """评价质量（权重4%）"""
    
    if good_review_rate >= 99:
        rate_score = 10
    elif good_review_rate >= 98:
        rate_score = 8 + (good_review_rate - 98) * 2
    elif good_review_rate >= 97:
        rate_score = 7 + (good_review_rate - 97) * 1
    elif good_review_rate >= 95:
        rate_score = 5 + (good_review_rate - 95) * 1
    elif good_review_rate >= 90:
        rate_score = 2 + (good_review_rate - 90) / 5 * 3
    else:
        rate_score = good_review_rate / 90 * 2
    
    if image_review_ratio >= 40:
        img_score = 10
    elif image_review_ratio >= 30:
        img_score = 8 + (image_review_ratio - 30) / 10 * 2
    elif image_review_ratio >= 20:
        img_score = 6 + (image_review_ratio - 20) / 10 * 2
    elif image_review_ratio >= 10:
        img_score = 3 + (image_review_ratio - 10) / 10 * 3
    else:
        img_score = image_review_ratio / 10 * 3
    
    # 核心差评扣分
    penalty = min(3, core_complaint_ratio * 10)
    
    score = (rate_score * 0.5 + img_score * 0.3 + 10 * 0.2) - penalty
    score = round(min(10, max(0, score)), 1)
    
    return {
        'score': score,
        'detail': {
            'good_review_rate': good_review_rate,
            'image_review_ratio': image_review_ratio,
            'core_complaint_ratio': core_complaint_ratio,
        }
    }


def score_wen_dajia(
    positive_answer_ratio: float,
    seller_answer_coverage: float,
) -> dict:
    """问大家（权重2%）"""
    if positive_answer_ratio >= 80:
        pos_score = 10
    elif positive_answer_ratio >= 60:
        pos_score = 7 + (positive_answer_ratio - 60) / 20 * 3
    elif positive_answer_ratio >= 40:
        pos_score = 4 + (positive_answer_ratio - 40) / 20 * 3
    elif positive_answer_ratio >= 20:
        pos_score = 2 + (positive_answer_ratio - 20) / 20 * 2
    else:
        pos_score = positive_answer_ratio / 20 * 2
    
    if seller_answer_coverage >= 90:
        seller_score = 10
    elif seller_answer_coverage >= 70:
        seller_score = 7 + (seller_answer_coverage - 70) / 20 * 3
    elif seller_answer_coverage >= 50:
        seller_score = 4 + (seller_answer_coverage - 50) / 20 * 3
    else:
        seller_score = seller_answer_coverage / 50 * 4
    
    score = pos_score * 0.7 + seller_score * 0.3
    score = round(min(10, max(0, score)), 1)
    
    return {
        'score': score,
        'detail': {
            'positive_answer_ratio': positive_answer_ratio,
            'seller_answer_coverage': seller_answer_coverage,
        }
    }


def score_customer_service(
    inquiry_conv_rate: float,
    avg_response_time_sec: float,
) -> dict:
    """客服询单转化（权重4%）"""
    
    if inquiry_conv_rate >= 85:
        conv_score = 10
    elif inquiry_conv_rate >= 70:
        conv_score = 8 + (inquiry_conv_rate - 70) / 15 * 2
    elif inquiry_conv_rate >= 55:
        conv_score = 6 + (inquiry_conv_rate - 55) / 15 * 2
    elif inquiry_conv_rate >= 40:
        conv_score = 4 + (inquiry_conv_rate - 40) / 15 * 2
    elif inquiry_conv_rate >= 20:
        conv_score = 2 + (inquiry_conv_rate - 20) / 20 * 2
    else:
        conv_score = inquiry_conv_rate / 20 * 2
    
    if avg_response_time_sec <= 10:
        resp_score = 10
    elif avg_response_time_sec <= 30:
        resp_score = 8 + (30 - avg_response_time_sec) / 20 * 2
    elif avg_response_time_sec <= 60:
        resp_score = 6 + (60 - avg_response_time_sec) / 30 * 2
    elif avg_response_time_sec <= 120:
        resp_score = 3 + (120 - avg_response_time_sec) / 60 * 3
    else:
        resp_score = max(0, 3 - (avg_response_time_sec - 120) / 120 * 3)
    
    score = conv_score * 0.7 + resp_score * 0.3
    score = round(min(10, max(0, score)), 1)
    
    return {
        'score': score,
        'detail': {
            'inquiry_conv_rate': inquiry_conv_rate,
            'avg_response_time_sec': avg_response_time_sec,
        }
    }


def score_market_acceptance(
    sell_through_rate: float,
    cart_add_rate: float,
    natural_conv_vs_industry: float = 1.0,  # 自然转化率/行业均值
) -> dict:
    """市场接受度（权重9%）"""
    
    if sell_through_rate >= 80:
        str_score = 10
    elif sell_through_rate >= 65:
        str_score = 8 + (sell_through_rate - 65) / 15 * 2
    elif sell_through_rate >= 45:
        str_score = 6 + (sell_through_rate - 45) / 20 * 2
    elif sell_through_rate >= 25:
        str_score = 4 + (sell_through_rate - 25) / 20 * 2
    elif sell_through_rate >= 10:
        str_score = 2 + (sell_through_rate - 10) / 15 * 2
    else:
        str_score = sell_through_rate / 10 * 2
    
    if cart_add_rate >= 12:
        cart_score = 10
    elif cart_add_rate >= 8:
        cart_score = 8 + (cart_add_rate - 8) / 4 * 2
    elif cart_add_rate >= 5:
        cart_score = 6 + (cart_add_rate - 5) / 3 * 2
    elif cart_add_rate >= 3:
        cart_score = 4 + (cart_add_rate - 3) / 2 * 2
    elif cart_add_rate >= 1:
        cart_score = 2 + (cart_add_rate - 1) / 2 * 2
    else:
        cart_score = cart_add_rate / 1 * 2
    
    # 自然转化率对比
    if natural_conv_vs_industry >= 1.5:
        nat_score = 10
    elif natural_conv_vs_industry >= 1.2:
        nat_score = 8 + (natural_conv_vs_industry - 1.2) / 0.3 * 2
    elif natural_conv_vs_industry >= 1.0:
        nat_score = 6 + (natural_conv_vs_industry - 1.0) / 0.2 * 2
    elif natural_conv_vs_industry >= 0.7:
        nat_score = 3 + (natural_conv_vs_industry - 0.7) / 0.3 * 3
    else:
        nat_score = natural_conv_vs_industry / 0.7 * 3
    
    score = str_score * 0.4 + cart_score * 0.3 + nat_score * 0.3
    score = round(min(10, max(0, score)), 1)
    
    return {
        'score': score,
        'detail': {
            'sell_through_rate': sell_through_rate,
            'cart_add_rate': cart_add_rate,
            'natural_conv_vs_industry': natural_conv_vs_industry,
        }
    }


def score_price_positioning(
    price_rank_percentile: float,
    promo_vs_daily_conv_ratio: float,
    price_complaint_ratio: float = 0,
) -> dict:
    """价格定位（权重10%）"""
    
    # price_rank_percentile: 核心SKU在同价位段的排名百分位 (0=最贵, 100=最便宜)
    if price_rank_percentile >= 60:  # 价格有竞争力
        rank_score = 8 + (price_rank_percentile - 60) / 40 * 2
    elif price_rank_percentile >= 40:
        rank_score = 5 + (price_rank_percentile - 40) / 20 * 3
    elif price_rank_percentile >= 20:
        rank_score = 3 + (price_rank_percentile - 20) / 20 * 2
    else:
        rank_score = price_rank_percentile / 20 * 3
    
    # 促销依赖度（倍数越高越依赖促销）
    if promo_vs_daily_conv_ratio <= 1.5:
        dep_score = 10
    elif promo_vs_daily_conv_ratio <= 2.0:
        dep_score = 8 + (2.0 - promo_vs_daily_conv_ratio) / 0.5 * 2
    elif promo_vs_daily_conv_ratio <= 3.0:
        dep_score = 5 + (3.0 - promo_vs_daily_conv_ratio) / 1.0 * 3
    elif promo_vs_daily_conv_ratio <= 5.0:
        dep_score = 2 + (5.0 - promo_vs_daily_conv_ratio) / 2.0 * 3
    else:
        dep_score = max(0, 2 - (promo_vs_daily_conv_ratio - 5) / 5 * 2)
    
    # 价格投诉扣分
    penalty = min(3, price_complaint_ratio * 10)
    
    score = rank_score * 0.5 + dep_score * 0.35 + 10 * 0.15 - penalty
    score = round(min(10, max(0, score)), 1)
    
    return {
        'score': score,
        'detail': {
            'price_rank_percentile': price_rank_percentile,
            'promo_vs_daily_conv_ratio': promo_vs_daily_conv_ratio,
            'price_complaint_ratio': price_complaint_ratio,
        }
    }


def score_sku_coverage(
    zero_sales_sku_ratio: float,
    top5_sales_concentration: float,
    price_band_coverage: int = 3,  # 1=不完整 3=一般 5=完整
) -> dict:
    """SKU覆盖（权重4%）"""
    
    if zero_sales_sku_ratio <= 10:
        zero_score = 10
    elif zero_sales_sku_ratio <= 15:
        zero_score = 8 + (15 - zero_sales_sku_ratio) / 5 * 2
    elif zero_sales_sku_ratio <= 30:
        zero_score = 5 + (30 - zero_sales_sku_ratio) / 15 * 3
    elif zero_sales_sku_ratio <= 50:
        zero_score = 2 + (50 - zero_sales_sku_ratio) / 20 * 3
    else:
        zero_score = max(0, 2 - (zero_sales_sku_ratio - 50) / 50 * 2)
    
    if top5_sales_concentration <= 50:
        conc_score = 10
    elif top5_sales_concentration <= 70:
        conc_score = 7 + (70 - top5_sales_concentration) / 20 * 3
    elif top5_sales_concentration <= 80:
        conc_score = 4 + (80 - top5_sales_concentration) / 10 * 3
    elif top5_sales_concentration <= 95:
        conc_score = 2 + (95 - top5_sales_concentration) / 15 * 2
    else:
        conc_score = max(0, 2 - (top5_sales_concentration - 95) / 5 * 2)
    
    coverage_score = price_band_coverage * 2
    
    score = zero_score * 0.35 + conc_score * 0.35 + coverage_score * 0.3
    score = round(min(10, max(0, score)), 1)
    
    return {
        'score': score,
        'detail': {
            'zero_sales_sku_ratio': zero_sales_sku_ratio,
            'top5_sales_concentration': top5_sales_concentration,
            'price_band_coverage_manual': price_band_coverage,
        }
    }


def score_sales_base(
    monthly_sales: int,
    same_price_rank: int,  # 同价位TOP10中的排名 (1=最好, 10=最差)
    sales_trend: int = 3,  # 1=下滑 3=持平 5=增长
) -> dict:
    """销量基数（权重4%）"""
    
    if monthly_sales >= 5000:
        sales_score = 10
    elif monthly_sales >= 1000:
        sales_score = 8 + (monthly_sales - 1000) / 4000 * 2
    elif monthly_sales >= 200:
        sales_score = 6 + (monthly_sales - 200) / 800 * 2
    elif monthly_sales >= 50:
        sales_score = 4 + (monthly_sales - 50) / 150 * 2
    elif monthly_sales >= 10:
        sales_score = 2 + (monthly_sales - 10) / 40 * 2
    else:
        sales_score = monthly_sales / 10 * 2
    
    rank_score = max(0, 10 - (same_price_rank - 1))
    trend_score = sales_trend * 2
    
    score = sales_score * 0.5 + rank_score * 0.3 + trend_score * 0.2
    score = round(min(10, max(0, score)), 1)
    
    return {
        'score': score,
        'detail': {
            'monthly_sales': monthly_sales,
            'same_price_rank': same_price_rank,
            'sales_trend': sales_trend,
        }
    }


def score_competitor_benchmark(
    core_metrics_vs_competitor: int,  # 1=全面落后 3=各有千秋 5=全面领先
    diff_points_count: int = 0,  # 差异化点数量
) -> dict:
    """竞品对标（权重5%）- 半自动"""
    metrics_score = core_metrics_vs_competitor * 2
    
    if diff_points_count >= 3:
        diff_score = 10
    elif diff_points_count >= 2:
        diff_score = 8
    elif diff_points_count >= 1:
        diff_score = 5
    else:
        diff_score = 2
    
    score = metrics_score * 0.6 + diff_score * 0.4
    score = round(min(10, max(0, score)), 1)
    
    return {
        'score': score,
        'detail': {
            'core_metrics_vs_competitor_manual': core_metrics_vs_competitor,
            'diff_points_count_manual': diff_points_count,
        }
    }


def score_dsr(
    desc_score: float,
    service_score: float,
    logistics_score: float,
    industry_avg: float = 4.75,
) -> dict:
    """DSR评分（权重3%）"""
    avg_dsr = (desc_score + service_score + logistics_score) / 3
    
    if avg_dsr >= 4.9:
        score = 10
    elif avg_dsr >= 4.8:
        score = 8 + (avg_dsr - 4.8) / 0.1 * 2
    elif avg_dsr >= industry_avg:
        score = 5 + (avg_dsr - industry_avg) / (4.8 - industry_avg) * 3
    elif avg_dsr >= 4.7:
        score = 4 + (avg_dsr - 4.7) / (industry_avg - 4.7) * 1
    else:
        score = max(0, (avg_dsr - 4.5) / 0.2 * 4)
    
    # 最短板扣分
    min_dsr = min(desc_score, service_score, logistics_score)
    if min_dsr < 4.5:
        score = min(score, 1)
    elif min_dsr < 4.7:
        score = min(score, score * 0.7)
    
    score = round(min(10, max(0, score)), 1)
    
    return {
        'score': score,
        'detail': {
            'desc_score': desc_score,
            'service_score': service_score,
            'logistics_score': logistics_score,
            'avg_dsr': round(avg_dsr, 2),
            'industry_avg': industry_avg,
        }
    }


def score_marketing(
    promo_frequency: float,  # 次/月
    promo_roi: float,
    daily_vs_promo_conv_ratio: float,  # 日常转化/促销转化
) -> dict:
    """营销方案（权重3%）"""
    
    # 频率（2-4次/月较好）
    if 2 <= promo_frequency <= 4:
        freq_score = 9
    elif 1 <= promo_frequency < 2:
        freq_score = 6
    elif 4 < promo_frequency <= 6:
        freq_score = 5
    elif promo_frequency > 6:
        freq_score = 3  # 打折成瘾
    else:
        freq_score = 2
    
    # ROI
    if promo_roi >= 5:
        roi_score = 10
    elif promo_roi >= 3:
        roi_score = 7 + (promo_roi - 3) / 2 * 3
    elif promo_roi >= 2:
        roi_score = 5 + (promo_roi - 2) * 2
    elif promo_roi >= 1:
        roi_score = 2 + (promo_roi - 1) * 3
    else:
        roi_score = max(0, promo_roi * 2)
    
    # 日常vs促销
    if daily_vs_promo_conv_ratio >= 0.7:  # 日常也不错
        balance_score = 10
    elif daily_vs_promo_conv_ratio >= 0.5:
        balance_score = 7 + (daily_vs_promo_conv_ratio - 0.5) / 0.2 * 3
    elif daily_vs_promo_conv_ratio >= 0.3:
        balance_score = 4 + (daily_vs_promo_conv_ratio - 0.3) / 0.2 * 3
    else:
        balance_score = daily_vs_promo_conv_ratio / 0.3 * 4
    
    score = freq_score * 0.2 + roi_score * 0.4 + balance_score * 0.4
    score = round(min(10, max(0, score)), 1)
    
    return {
        'score': score,
        'detail': {
            'promo_frequency': promo_frequency,
            'promo_roi': promo_roi,
            'daily_vs_promo_conv_ratio': daily_vs_promo_conv_ratio,
        }
    }


def score_service_promise(
    warranty_months: int,
    has_7day_return: bool,
    dispute_rate: float = 0,
) -> dict:
    """服务承诺（权重2%）"""
    
    if warranty_months >= 60:
        warranty_score = 10
    elif warranty_months >= 36:
        warranty_score = 8 + (warranty_months - 36) / 24 * 2
    elif warranty_months >= 12:
        warranty_score = 6 + (warranty_months - 12) / 24 * 2
    elif warranty_months >= 6:
        warranty_score = 4 + (warranty_months - 6) / 6 * 2
    else:
        warranty_score = warranty_months / 6 * 4
    
    return_score = 10 if has_7day_return else 3
    
    dispute_penalty = min(3, dispute_rate * 10)
    
    score = warranty_score * 0.35 + return_score * 0.35 + 10 * 0.15 - dispute_penalty * 0.15 + 1
    score = round(min(10, max(0, score)), 1)
    
    return {
        'score': score,
        'detail': {
            'warranty_months': warranty_months,
            'has_7day_return': has_7day_return,
            'dispute_rate': dispute_rate,
        }
    }


def score_shipping(
    shipping_on_time_rate: float,
    free_shipping: bool,
    logistics_complaint_ratio: float = 0,
) -> dict:
    """发货/包邮（权重2%）"""
    
    if shipping_on_time_rate >= 98:
        time_score = 10
    elif shipping_on_time_rate >= 95:
        time_score = 8 + (shipping_on_time_rate - 95) / 3 * 2
    elif shipping_on_time_rate >= 90:
        time_score = 6 + (shipping_on_time_rate - 90) / 5 * 2
    elif shipping_on_time_rate >= 80:
        time_score = 3 + (shipping_on_time_rate - 80) / 10 * 3
    else:
        time_score = shipping_on_time_rate / 80 * 3
    
    free_score = 10 if free_shipping else 4
    
    if logistics_complaint_ratio <= 1:
        complaint_score = 10
    elif logistics_complaint_ratio <= 3:
        complaint_score = 7 + (3 - logistics_complaint_ratio) / 2 * 3
    elif logistics_complaint_ratio <= 5:
        complaint_score = 4 + (5 - logistics_complaint_ratio) / 2 * 3
    elif logistics_complaint_ratio <= 15:
        complaint_score = 2 + (15 - logistics_complaint_ratio) / 10 * 2
    else:
        complaint_score = max(0, 2 - (logistics_complaint_ratio - 15) / 10 * 2)
    
    score = time_score * 0.35 + free_score * 0.3 + complaint_score * 0.35
    score = round(min(10, max(0, score)), 1)
    
    return {
        'score': score,
        'detail': {
            'shipping_on_time_rate': shipping_on_time_rate,
            'free_shipping': free_shipping,
            'logistics_complaint_ratio': logistics_complaint_ratio,
        }
    }


# ============================================================
# 二、维度权重与元数据
# ============================================================

DIMENSIONS = [
    {'id': 'traffic_quality',       'name': '流量质量精准度',  'weight': 0.13, 'layer': '流量端',     'scoring_func': score_traffic_quality},
    {'id': 'position_rank',         'name': '位置排名',        'weight': 0.03, 'layer': '流量端',     'scoring_func': score_position_rank},
    {'id': 'time_node',             'name': '时间节点',        'weight': 0.03, 'layer': '流量端',     'scoring_func': score_time_node},
    {'id': 'traffic_page_match',    'name': '流量-页面匹配度', 'weight': 0.20, 'layer': '转化端',     'scoring_func': score_traffic_page_match},
    {'id': 'main_image_ctr',        'name': '主图点击率',      'weight': 0.05, 'layer': '转化端',     'scoring_func': score_main_image_ctr},
    {'id': 'detail_page_logic',     'name': '详情页五层逻辑',  'weight': 0.04, 'layer': '转化端',     'scoring_func': score_detail_page_logic},
    {'id': 'review_quality',        'name': '评价质量',        'weight': 0.04, 'layer': '转化端',     'scoring_func': score_review_quality},
    {'id': 'wen_dajia',             'name': '问大家',          'weight': 0.02, 'layer': '转化端',     'scoring_func': score_wen_dajia},
    {'id': 'customer_service',      'name': '客服询单转化',    'weight': 0.04, 'layer': '转化端',     'scoring_func': score_customer_service},
    {'id': 'market_acceptance',     'name': '市场接受度',      'weight': 0.09, 'layer': '产品端',     'scoring_func': score_market_acceptance},
    {'id': 'price_positioning',     'name': '价格定位',        'weight': 0.10, 'layer': '产品端',     'scoring_func': score_price_positioning},
    {'id': 'sku_coverage',          'name': 'SKU覆盖',         'weight': 0.04, 'layer': '产品端',     'scoring_func': score_sku_coverage},
    {'id': 'sales_base',            'name': '销量基数',        'weight': 0.04, 'layer': '产品端',     'scoring_func': score_sales_base},
    {'id': 'competitor_benchmark',  'name': '竞品对标',        'weight': 0.05, 'layer': '服务+竞争端', 'scoring_func': score_competitor_benchmark},
    {'id': 'dsr',                   'name': 'DSR评分',         'weight': 0.03, 'layer': '服务+竞争端', 'scoring_func': score_dsr},
    {'id': 'marketing',             'name': '营销方案',        'weight': 0.03, 'layer': '服务+竞争端', 'scoring_func': score_marketing},
    {'id': 'service_promise',       'name': '服务承诺',        'weight': 0.02, 'layer': '服务+竞争端', 'scoring_func': score_service_promise},
    {'id': 'shipping',              'name': '发货/包邮',       'weight': 0.02, 'layer': '服务+竞争端', 'scoring_func': score_shipping},
]

LAYERS = {
    '流量端':       {'weight': 0.19, 'dims': ['traffic_quality', 'position_rank', 'time_node']},
    '转化端':       {'weight': 0.39, 'dims': ['traffic_page_match', 'main_image_ctr', 'detail_page_logic', 'review_quality', 'wen_dajia', 'customer_service']},
    '产品端':       {'weight': 0.27, 'dims': ['market_acceptance', 'price_positioning', 'sku_coverage', 'sales_base']},
    '服务+竞争端':  {'weight': 0.15, 'dims': ['competitor_benchmark', 'dsr', 'marketing', 'service_promise', 'shipping']},
}

LAYER_OPTIMIZATION = {
    '流量端': '调流量：优化关键词、精准人群溢价、卡位排名',
    '转化端': '调页面+信任：优化详情页、测主图、做评价、练客服',
    '产品端': '调产品：选品调整、价格策略、SKU优化',
    '服务+竞争端': '补服务+找差异：升级服务承诺、做差异化',
}


# ============================================================
# 三、诊断引擎
# ============================================================

class DiagnosisEngine:
    """18维度全链路诊断引擎 V2.0"""
    
    # 维度数据来源标记说明
    SOURCE_LABELS = {
        'real': '✅真实数据',
        'semi': '⚠️半自动',
        'auto': '🤖自动计算',
        'missing': '❌缺数据',
    }
    
    # 每个维度的参数来源定义（哪些参数是真实数据、哪些是半自动）
    # 未在此定义的参数默认为 semi
    DIM_PARAM_SOURCES = {
        'traffic_page_match': {
            'precise_bounce_rate': 'real',
            'top20_keyword_coverage': 'semi',
            'has_channel_landing_pages': 'semi',
        },
        'traffic_quality': {
            'precise_keyword_ratio': 'semi',
            'paid_keyword_quality_score': 'semi',
            'audience_overlap': 'semi',
            'search_traffic_ratio': 'real',
            'recommend_traffic_ratio': 'real',
            'content_traffic_ratio': 'real',
            'cart_fav_traffic_ratio': 'real',
            'recommend_audience_overlap': 'semi',
            'recommend_fav_cart_rate': 'semi',
            'content_audience_overlap': 'semi',
            'content_bounce_rate': 'semi',
            'cart_conv_rate': 'semi',
            'fav_conv_rate': 'semi',
        },
        'time_node': {
            'current_date_str': 'auto',
            'industry_search_trend': 'semi',
        },
        'market_acceptance': {
            'sell_through_rate': 'semi',
            'cart_add_rate': 'real',  # 自然搜索加购率，来自生意参谋真实数据
            'natural_conv_vs_industry': 'semi',  # 需要同行同层链接转化率，搜索词站内转化率口径不同不能直接用
        },
        'sales_base': {
            'monthly_sales': 'real',
            'same_price_rank': 'semi',
            'sales_trend': 'semi',
        },
        'dsr': {
            'desc_score': 'semi',
            'service_score': 'semi',
            'logistics_score': 'semi',
            'industry_avg': 'semi',  # 需要行业数据
        },
    }
    
    # 广告稀释预警阈值
    AD_TRAFFIC_WARN_THRESHOLD = 0.70
    
    def __init__(self, raw_data: dict, data_sources: dict = None):
        """
        raw_data: 字典，key为维度id，value为该维度的输入参数字典
        data_sources: 可选，标记每个参数的数据来源。
            格式: {维度id: {参数名: 'real'|'semi'|'auto'|'missing'}}
            未提供的维度使用 DIM_PARAM_SOURCES 默认值
        
        示例:
          engine = DiagnosisEngine(
              raw_data={
                  'traffic_page_match': {
                      'precise_bounce_rate': 91.04,
                      'top20_keyword_coverage': 45,
                  },
                  ...
              },
              data_sources={
                  'traffic_page_match': {
                      'precise_bounce_rate': 'real',
                      'top20_keyword_coverage': 'semi',
                  },
                  ...
              }
          )
        """
        self.raw_data = raw_data
        self.data_sources = data_sources or {}
        self.dim_map = {d['id']: d for d in DIMENSIONS}
        self.warnings = []  # 校验警告
    
    def _get_param_source(self, dim_id: str, param_name: str) -> str:
        """获取参数的数据来源标记"""
        # 优先用外部传入的 sources
        if dim_id in self.data_sources and param_name in self.data_sources[dim_id]:
            return self.data_sources[dim_id][param_name]
        # 其次用默认定义
        if dim_id in self.DIM_PARAM_SOURCES and param_name in self.DIM_PARAM_SOURCES[dim_id]:
            return self.DIM_PARAM_SOURCES[dim_id][param_name]
        # 默认 semi
        return 'semi'
    
    def _get_dim_source_label(self, dim_id: str, dim_data: dict) -> str:
        """获取维度的整体数据来源标记（取最弱的来源）"""
        if not dim_data:
            return 'missing'
        sources = []
        for param_name in dim_data:
            sources.append(self._get_param_source(dim_id, param_name))
        # 优先级: missing > semi > auto > real
        priority = {'missing': 0, 'semi': 1, 'auto': 2, 'real': 3}
        weakest = min(sources, key=lambda s: priority.get(s, 1))
        return weakest
    
    def _validate_data(self):
        """校验输入数据的语义正确性"""
        self.warnings = []
        
        # === 校验1: promo_vs_daily_conv_ratio 语义 ===
        pp = self.raw_data.get('price_positioning', {})
        if pp:
            promo_ratio = pp.get('promo_vs_daily_conv_ratio', 0)
            # 如果值 > 10，很可能是把"广告转化/自然转化"填进来了
            if promo_ratio > 10:
                self.warnings.append(
                    f"⚠️ price_positioning.promo_vs_daily_conv_ratio={promo_ratio} "
                    f"异常偏高！此参数应为「促销时转化率/日常转化率」（通常1.5-5倍），"
                    f"不是「广告转化率/自然转化率」。广告vs自然的差异反映的是流量精准度，不是价格力。"
                )
        
        # === 校验2: 广告稀释检测 ===
        tq = self.raw_data.get('traffic_quality', {})
        if tq:
            search_ratio = tq.get('search_traffic_ratio', 0)
            recommend_ratio = tq.get('recommend_traffic_ratio', 0)
            content_ratio = tq.get('content_traffic_ratio', 0)
            cart_fav_ratio = tq.get('cart_fav_traffic_ratio', 0)
            natural_total = search_ratio + recommend_ratio + content_ratio + cart_fav_ratio
            ad_ratio = 1 - natural_total
            
            if ad_ratio > self.AD_TRAFFIC_WARN_THRESHOLD:
                self.warnings.append(
                    f"🔴 广告流量占比 {ad_ratio:.0%} 超过 {self.AD_TRAFFIC_WARN_THRESHOLD:.0%} 阈值！"
                    f"整体转化率、加购率等指标被广告严重稀释，请优先使用分渠道数据（如自然搜索转化率），"
                    f"不要用整体数据判断产品力。"
                )
        
        # === 校验3: market_acceptance.natural_conv_vs_industry 需要同行同层数据 ===
        ma = self.raw_data.get('market_acceptance', {})
        if ma and 'natural_conv_vs_industry' in ma:
            source = self._get_param_source('market_acceptance', 'natural_conv_vs_industry')
            if source == 'semi':
                self.warnings.append(
                    "⚠️ market_acceptance.natural_conv_vs_industry 缺少真实行业数据。"
                    "此参数需要生意参谋「市场洞察」的同行同层链接转化率，"
                    "不是搜索词站内转化率（口径不同：站内转化率包含所有店铺成交，"
                    "天然高于单链接转化率，不能直接做比值）。"
                    "估算值会导致市场接受度评分严重偏差。"
                )
    
    def run(self) -> dict:
        """执行完整诊断，返回报告"""
        # 0. 数据校验
        self._validate_data()
        
        # 1. 逐维度评分
        dim_results = {}
        for d in DIMENSIONS:
            did = d['id']
            if did in self.raw_data and self.raw_data[did]:
                try:
                    result = d['scoring_func'](**self.raw_data[did])
                    source_label = self._get_dim_source_label(did, self.raw_data[did])
                    dim_results[did] = {
                        'name': d['name'],
                        'weight': d['weight'],
                        'layer': d['layer'],
                        'score': result['score'],
                        'weighted_score': round(result['score'] * d['weight'], 3),
                        'detail': result.get('detail', {}),
                        'data_source': source_label,
                        'source_label': self.SOURCE_LABELS.get(source_label, source_label),
                    }
                except Exception as e:
                    dim_results[did] = {
                        'name': d['name'],
                        'weight': d['weight'],
                        'layer': d['layer'],
                        'score': None,
                        'weighted_score': 0,
                        'detail': {'error': str(e)},
                        'data_source': 'missing',
                        'source_label': '❌评分失败',
                    }
            else:
                dim_results[did] = {
                    'name': d['name'],
                    'weight': d['weight'],
                    'layer': d['layer'],
                    'score': None,
                    'weighted_score': 0,
                    'detail': {'missing': True},
                    'data_source': 'missing',
                    'source_label': '❌缺数据',
                }
        
        # 2. 分层得分
        layer_results = {}
        for layer_name, layer_info in LAYERS.items():
            scores = [dim_results[did]['score'] for did in layer_info['dims'] if dim_results[did]['score'] is not None]
            weighted_sum = sum(dim_results[did]['weighted_score'] for did in layer_info['dims'])
            if scores:
                layer_avg = round(weighted_sum / layer_info['weight'], 1)
            else:
                layer_avg = None
            layer_results[layer_name] = {
                'weight': layer_info['weight'],
                'weighted_sum': round(weighted_sum, 3),
                'avg_score': layer_avg,
                'status': self._judge(layer_avg),
                'dimension_count': len(layer_info['dims']),
                'scored_count': len(scores),
            }
        
        # 3. 综合得分
        total_weighted = sum(v['weighted_score'] for v in dim_results.values())
        
        # 4. 最薄弱环节
        scored_layers = {k: v for k, v in layer_results.items() if v['avg_score'] is not None}
        weakest_layer = min(scored_layers, key=lambda k: scored_layers[k]['avg_score']) if scored_layers else None
        
        scored_dims = {k: v for k, v in dim_results.items() if v['score'] is not None}
        weakest_dim = min(scored_dims, key=lambda k: scored_dims[k]['score']) if scored_dims else None
        
        # 5. 优先级排序
        priority_list = sorted(
            [(k, v) for k, v in dim_results.items() if v['score'] is not None],
            key=lambda x: x[1]['score']
        )
        
        # 6. 数据可靠度统计
        source_stats = {'real': 0, 'semi': 0, 'auto': 0, 'missing': 0}
        for did, dr in dim_results.items():
            s = dr.get('data_source', 'missing')
            source_stats[s] = source_stats.get(s, 0) + 1
        
        return {
            'total_score': round(total_weighted, 1),
            'total_status': self._judge(total_weighted),
            'layer_results': layer_results,
            'dim_results': dim_results,
            'weakest_layer': weakest_layer,
            'weakest_dim': weakest_dim,
            'priority_list': priority_list,
            'warnings': self.warnings,
            'source_stats': source_stats,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
    
    @staticmethod
    def _judge(score: Optional[float]) -> str:
        if score is None:
            return '未评分'
        if score >= 8:
            return '健康'
        elif score >= 6:
            return '亚健康'
        elif score >= 4:
            return '需优化'
        else:
            return '严重'
    
    @staticmethod
    def generate_report(result: dict) -> str:
        """生成Markdown诊断报告（V2.0 含数据来源标记和校验警告）"""
        lines = []
        lines.append('# 店铺全链路诊断报告')
        lines.append(f'\n> 诊断时间：{result["timestamp"]}')
        lines.append(f'> 引擎版本：V2.0')
        lines.append('')
        
        # 数据可靠度
        ss = result.get('source_stats', {})
        real_n = ss.get('real', 0)
        semi_n = ss.get('semi', 0)
        auto_n = ss.get('auto', 0)
        missing_n = ss.get('missing', 0)
        total_dims = real_n + semi_n + auto_n + missing_n
        lines.append(f'> 数据可靠度：✅真实{real_n}个 | ⚠️半自动{semi_n}个 | 🤖自动{auto_n}个 | ❌缺数据{missing_n}个（共{total_dims}维度）')
        
        # 校验警告
        warnings = result.get('warnings', [])
        if warnings:
            lines.append('')
            lines.append('### ⚠️ 数据校验警告')
            for w in warnings:
                lines.append(f'- {w}')
        
        lines.append('')
        
        # 一、总览
        lines.append('## 一、总览')
        lines.append('')
        lines.append(f'- **综合得分**：{result["total_score"]} / 10（{result["total_status"]}）')
        if result['weakest_layer']:
            lines.append(f'- **最薄弱环节**：{result["weakest_layer"]}')
        if result['weakest_dim']:
            wd = result['dim_results'][result['weakest_dim']]
            lines.append(f'- **最短板维度**：{wd["name"]}（{wd["score"]}分）')
        lines.append('')
        
        # 二、分层得分
        lines.append('## 二、分层得分')
        lines.append('')
        lines.append('| 层级 | 权重 | 加权得分 | 层级均分 | 判定 |')
        lines.append('|------|------|---------|---------|------|')
        for layer_name, lr in result['layer_results'].items():
            lines.append(f'| {layer_name} | {lr["weight"]:.0%} | {lr["weighted_sum"]:.2f} | {lr["avg_score"] or "—"} | {lr["status"]} |')
        lines.append('')
        
        # 三、各维度得分（从低到高）含数据来源
        lines.append('## 三、各维度得分（从低到高）')
        lines.append('')
        lines.append('| 排名 | 维度 | 所属层级 | 评分 | 权重 | 数据来源 | 判定 |')
        lines.append('|------|------|---------|------|------|---------|------|')
        for i, (did, dr) in enumerate(result['priority_list'], 1):
            judge = DiagnosisEngine._judge(dr['score'])
            source = dr.get('source_label', '⚠️半自动')
            lines.append(f'| {i} | {dr["name"]} | {dr["layer"]} | {dr["score"]} | {dr["weight"]:.0%} | {source} | {judge} |')
        lines.append('')
        
        # 四、优先优化建议
        lines.append('## 四、优先优化建议 Top 3')
        lines.append('')
        for i, (did, dr) in enumerate(result['priority_list'][:3], 1):
            priority = '紧急' if dr['score'] <= 3 else '重要' if dr['score'] <= 5 else '关注'
            opt = LAYER_OPTIMIZATION.get(dr['layer'], '')
            source = dr.get('source_label', '')
            lines.append(f'{i}. **【{priority}】{dr["name"]}**（{dr["score"]}分，{source}）→ {opt}')
        lines.append('')
        
        # 五、交叉诊断
        lines.append('## 五、交叉诊断')
        lines.append('')
        tq = result['dim_results'].get('traffic_quality', {}).get('score')
        tpm = result['dim_results'].get('traffic_page_match', {}).get('score')
        if tq is not None and tpm is not None:
            if tq >= 6 and tpm < 5:
                lines.append('- ⚠️ **流量精准度尚可但页面匹配度低** → 问题在页面，不要冤枉流量！重点优化详情页卖点优先级和渠道落地页。')
            elif tq < 5 and tpm >= 6:
                lines.append('- ⚠️ **页面匹配度尚可但流量精准度低** → 问题在流量，不要冤枉页面！重点优化关键词和人群定向。')
            elif tq >= 6 and tpm >= 6:
                lines.append('- ✅ 流量精准度和页面匹配度双高，流量端+转化端配合良好。')
            else:
                lines.append('- 🔴 流量精准度和页面匹配度双低，全链路问题，建议先修流量再修页面。')
        
        ma = result['dim_results'].get('market_acceptance', {}).get('score')
        sb = result['dim_results'].get('sales_base', {}).get('score')
        if ma is not None and sb is not None:
            if ma >= 6 and sb < 5:
                lines.append('- ⚠️ **市场接受度好但销量基数低** → 不是产品问题，是曝光/流量问题。')
            elif ma < 5 and sb >= 6:
                lines.append('- ⚠️ **销量靠推广硬撑但市场接受度低** → 不可持续，回归产品力。')
        lines.append('')
        
        # 六、各维度详细诊断
        lines.append('## 六、各维度详细数据')
        lines.append('')
        for did, dr in result['priority_list']:
            source = dr.get('source_label', '')
            lines.append(f'### {dr["name"]}（{dr["score"]}分，权重{dr["weight"]:.0%}，{source}）')
            if 'detail' in dr and dr['detail']:
                for k, v in dr['detail'].items():
                    lines.append(f'- {k}: {v}')
            lines.append('')
        
        return '\n'.join(lines)
    
    @staticmethod
    def save_report(result: dict, filepath: str):
        """保存报告为Markdown文件"""
        report = DiagnosisEngine.generate_report(result)
        os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
        return filepath


# ============================================================
# 四、示例数据 & 测试
# ============================================================

SAMPLE_DATA = {
    'traffic_quality': {
        'precise_keyword_ratio': 62,
        'paid_keyword_quality_score': 7.2,
        'audience_overlap': 65,
        'recommend_audience_overlap': 55,
        'recommend_fav_cart_rate': 4.5,
        'content_audience_overlap': 48,
        'content_bounce_rate': 55,
        'cart_conv_rate': 12,
        'fav_conv_rate': 8,
        'search_traffic_ratio': 0.55,
        'recommend_traffic_ratio': 0.20,
        'content_traffic_ratio': 0.10,
        'cart_fav_traffic_ratio': 0.15,
    },
    'position_rank': {
        'core_keyword_rank_page': 3,
        'natural_traffic_ratio': 45,
    },
    'time_node': {
        'current_date_str': '2026-05-25',
        'industry_search_trend': 3,
    },
    'traffic_page_match': {
        'precise_bounce_rate': 52,
        'top20_keyword_coverage': 65,
        'has_channel_landing_pages': False,
    },
    'main_image_ctr': {
        'main_image_ctr': 3.2,
        'industry_avg_ctr': 3.5,
    },
    'detail_page_logic': {
        'first_3_screen_stay_ratio': 55,
        'page_read_completion': 22,
        'logic_completeness': 3,
    },
    'review_quality': {
        'good_review_rate': 96.5,
        'image_review_ratio': 18,
        'core_complaint_ratio': 5,
    },
    'wen_dajia': {
        'positive_answer_ratio': 55,
        'seller_answer_coverage': 60,
    },
    'customer_service': {
        'inquiry_conv_rate': 48,
        'avg_response_time_sec': 45,
    },
    'market_acceptance': {
        'sell_through_rate': 42,
        'cart_add_rate': 4.5,
        'natural_conv_vs_industry': 0.9,
    },
    'price_positioning': {
        'price_rank_percentile': 45,
        'promo_vs_daily_conv_ratio': 2.8,
        'price_complaint_ratio': 8,
    },
    'sku_coverage': {
        'zero_sales_sku_ratio': 25,
        'top5_sales_concentration': 78,
        'price_band_coverage': 3,
    },
    'sales_base': {
        'monthly_sales': 150,
        'same_price_rank': 6,
        'sales_trend': 3,
    },
    'competitor_benchmark': {
        'core_metrics_vs_competitor': 3,
        'diff_points_count': 1,
    },
    'dsr': {
        'desc_score': 4.8,
        'service_score': 4.78,
        'logistics_score': 4.75,
        'industry_avg': 4.75,
    },
    'marketing': {
        'promo_frequency': 2,
        'promo_roi': 2.5,
        'daily_vs_promo_conv_ratio': 0.4,
    },
    'service_promise': {
        'warranty_months': 12,
        'has_7day_return': True,
        'dispute_rate': 2,
    },
    'shipping': {
        'shipping_on_time_rate': 92,
        'free_shipping': True,
        'logistics_complaint_ratio': 3,
    },
}


if __name__ == '__main__':
    engine = DiagnosisEngine(SAMPLE_DATA)
    result = engine.run()
    
    print(f'综合得分: {result["total_score"]} / 10 ({result["total_status"]})')
    print(f'最薄弱环节: {result["weakest_layer"]}')
    print(f'最短板维度: {result["dim_results"][result["weakest_dim"]]["name"]} ({result["dim_results"][result["weakest_dim"]]["score"]}分)')
    print()
    
    print('分层得分:')
    for layer_name, lr in result['layer_results'].items():
        print(f'  {layer_name}: {lr["avg_score"]}分 ({lr["status"]})')
    print()
    
    print('优先优化 Top 3:')
    for i, (did, dr) in enumerate(result['priority_list'][:3], 1):
        print(f'  {i}. {dr["name"]} - {dr["score"]}分 ({dr["layer"]})')
    
    # 生成报告
    report_path = './电商诊断系统/output/示例诊断报告.md'
    DiagnosisEngine.save_report(result, report_path)
    print(f'\n报告已保存: {report_path}')
