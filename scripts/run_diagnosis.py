#!/usr/bin/env python3
"""
电商链接诊断 - 入口脚本
接收扁平JSON数据，自动映射为引擎所需的嵌套结构，运行诊断，输出结论

V6更新 (2026-06-10):
  - 新增推广报表解析（ad_report_path + product_prefix）
  - 归因修正：剥离自然流量转化金额
  - 拉新/收割分层评价
  - 退款/秒退分析
  - 成交新客占比正确解读
"""

import sys
import json
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scoring_engine import DiagnosisEngine
from scoring_engine.conclusion_generator import ConclusionGenerator
from scoring_engine.ad_parser import AdReportParser, AdDiagnosisGenerator


# 行业默认值
CATEGORY_DEFAULTS = {
    '净水壶': {'avg_ctr': 3.5, 'avg_conv': 2.5, 'avg_bounce': 55, 'avg_cart_rate': 6.5, 'avg_price': 300},
    '女装': {'avg_ctr': 4.0, 'avg_conv': 3.0, 'avg_bounce': 45, 'avg_cart_rate': 11.0, 'avg_price': 150},
    '食品': {'avg_ctr': 3.0, 'avg_conv': 5.0, 'avg_bounce': 40, 'avg_cart_rate': 9.0, 'avg_price': 80},
    '3C数码': {'avg_ctr': 2.5, 'avg_conv': 2.0, 'avg_bounce': 55, 'avg_cart_rate': 7.5, 'avg_price': 800},
}
DEFAULT_CATEGORY = {'avg_ctr': 3.0, 'avg_conv': 2.5, 'avg_bounce': 50, 'avg_cart_rate': 7.0, 'avg_price': 200}


def build_raw_data(input_data: dict) -> dict:
    """将用户输入的扁平数据映射为引擎所需的嵌套结构"""
    d = input_data  # 简写
    cat = d.get('category', '净水壶')
    defaults = CATEGORY_DEFAULTS.get(cat, DEFAULT_CATEGORY)
    
    raw_data = {
        'traffic_quality': {
            'precise_keyword_ratio': d.get('precise_keyword_ratio', 50),
            'paid_keyword_quality_score': d.get('paid_keyword_quality_score', 5),
            'audience_overlap': d.get('audience_overlap', 30),
            'search_traffic_ratio': d.get('search_traffic_ratio', 0.55),
            'recommend_traffic_ratio': d.get('recommend_traffic_ratio', 0.20),
            'content_traffic_ratio': d.get('content_traffic_ratio', 0.10),
            'cart_fav_traffic_ratio': d.get('cart_fav_traffic_ratio', 0.15),
        },
        'position_rank': {
            'core_keyword_rank_page': d.get('core_keyword_rank_page', 3),
            'natural_traffic_ratio': d.get('search_traffic_ratio', 0.55),
        },
        'time_node': {
            'current_date_str': d.get('current_date', None),
            'industry_search_trend': d.get('industry_search_trend', 'stable'),
        },
        'traffic_page_match': {
            'precise_bounce_rate': d.get('bounce_rate', defaults['avg_bounce']),
            'top20_keyword_coverage': d.get('top20_keyword_coverage', 60),
            'has_channel_landing_pages': d.get('has_channel_landing_pages', False),
            'ad_traffic_ratio': d.get('ad_traffic_ratio', 0.5),
            'natural_bounce_rate': d.get('natural_bounce_rate', None),
        },
        'main_image_ctr': {
            'main_image_ctr': d.get('main_image_ctr', defaults['avg_ctr']),
            'industry_avg_ctr': d.get('industry_avg_ctr', defaults['avg_ctr']),
        },
        'detail_page_logic': {
            'avg_stay_duration': d.get('avg_stay_duration', 45),
            'detail_scroll_depth': d.get('detail_scroll_depth', 0.4),
        },
        'review_quality': {
            'review_positive_rate': d.get('review_positive_rate', 0.85),
            'review_with_content_rate': d.get('review_with_content_rate', 0.3),
        },
        'wen_dajia': {
            'wen_dajia_reply_rate': d.get('wen_dajia_reply_rate', 0.5),
        },
        'customer_service': {
            'inquiry_conv_rate': d.get('inquiry_conv_rate', 40),
        },
        'market_acceptance': {
            'sell_through_rate': d.get('sell_through_rate', None),
            'cart_add_rate': d.get('cart_rate', defaults['avg_cart_rate']),
            'natural_conv_vs_industry': d.get('natural_conv_vs_industry', None),
        },
        'price_positioning': {
            'price_rank_percentile': d.get('price_rank_percentile', 50),
            'promo_vs_daily_conv_ratio': d.get('promo_vs_daily_conv_ratio', 2.0),
        },
        'sku_coverage': {
            'zero_sales_sku_ratio': d.get('zero_sales_sku_ratio', 0.2),
            'sku_price_range_ratio': d.get('sku_price_range_ratio', 0.6),
        },
        'sales_base': {
            'monthly_sales': d.get('monthly_sales', 100),
            'same_price_rank': d.get('same_price_rank', None),
            'sales_trend': d.get('sales_trend', 'stable'),
        },
        'competitor_benchmark': {
            'competitor_gap': d.get('competitor_gap', 0.5),
        },
        'dsr': {
            'desc_score': d.get('desc_score', None),
            'service_score': d.get('service_score', None),
            'logistics_score': d.get('logistics_score', None),
            'industry_avg': d.get('industry_avg_dsr', None),
        },
        'marketing': {
            'promo_roi': d.get('promo_roi', 3.0),
        },
        'service_promise': {
            'service_promise_score': d.get('service_promise_score', 7),
        },
        'shipping': {
            'shipping_score': d.get('shipping_score', 7),
        },
    }
    
    # 移除None值的参数（让引擎使用默认值）
    for dim_id, params in raw_data.items():
        raw_data[dim_id] = {k: v for k, v in params.items() if v is not None}
    
    return raw_data


def run_diagnosis(input_data: dict) -> dict:
    """运行完整诊断流程（V6：含推广深度分析）"""
    raw_data = build_raw_data(input_data)
    
    engine = DiagnosisEngine(raw_data=raw_data)
    result = engine.run()
    
    # 构造结论生成器的额外上下文
    category = input_data.get('category', '净水壶')
    # 标记数据来源：用户提供的标✅，引擎默认的标⚠️
    data_sources = {}
    user_provided_keys = set(input_data.keys()) - {'product_name', 'category', 'current_date', 'ad_report_path', 'product_prefix'}
    
    extra_context = {
        'product_name': input_data.get('product_name', '未命名商品'),
        'category': category,
        'daily_visitors': input_data.get('daily_visitors'),
        'conv_rate': input_data.get('conv_rate'),
        'natural_conv_rate': input_data.get('natural_conv_rate'),
        'ad_conv_rate': input_data.get('ad_conv_rate'),
        'ad_ratio': input_data.get('ad_traffic_ratio'),
        'ad_cart_rate': input_data.get('ad_cart_rate'),
        'cpc': input_data.get('cpc'),
        'ad_roi': input_data.get('ad_roi'),
        'price': input_data.get('price'),
        'monthly_sales': input_data.get('monthly_sales'),
        'bounce_rate': input_data.get('bounce_rate'),
        'refund_rate': input_data.get('refund_rate'),
        'instant_refund': input_data.get('instant_refund', False),
        'current_month': input_data.get('current_month', 6),
        # 数据来源标记
        'data_sources': {
            'daily_visitors': 'user' if 'daily_visitors' in user_provided_keys else 'default',
            'conv_rate': 'user' if 'conv_rate' in user_provided_keys else 'default',
            'natural_conv_rate': 'user' if 'natural_conv_rate' in user_provided_keys else 'default',
            'ad_conv_rate': 'user' if 'ad_conv_rate' in user_provided_keys else 'default',
            'ad_ratio': 'user' if 'ad_traffic_ratio' in user_provided_keys else 'default',
            'ad_cart_rate': 'user' if 'ad_cart_rate' in user_provided_keys else 'default',
            'cpc': 'user' if 'cpc' in user_provided_keys else 'default',
            'ad_roi': 'user' if 'ad_roi' in user_provided_keys else 'default',
            'price': 'user' if 'price' in user_provided_keys else 'default',
            'monthly_sales': 'user' if 'monthly_sales' in user_provided_keys else 'default',
            'bounce_rate': 'user' if 'bounce_rate' in user_provided_keys else 'default',
            'top20_keyword_coverage': 'user' if 'top20_keyword_coverage' in user_provided_keys else 'default',
        },
    }
    
    # V6新增：推广深度诊断
    ad_diagnosis = None
    ad_report_path = input_data.get('ad_report_path')
    product_prefix = input_data.get('product_prefix')
    
    if ad_report_path and os.path.exists(ad_report_path):
        parser = AdReportParser(ad_report_path, product_prefix)
        ad_data = parser.parse()
        
        if 'error' not in ad_data:
            # 推广上下文（结合商品数据）
            product_context = {
                'natural_conv_rate': input_data.get('natural_conv_rate'),
                'ad_traffic_ratio': input_data.get('ad_traffic_ratio'),
                'price': input_data.get('price'),
                'refund_rate': input_data.get('refund_rate'),
                'instant_refund': input_data.get('instant_refund', False),
            }
            generator = AdDiagnosisGenerator(ad_data, product_context)
            ad_diagnosis = generator.generate()
    
    generator = ConclusionGenerator(engine_result=result, extra_context=extra_context, ad_diagnosis=ad_diagnosis)
    conclusion = generator.generate()
    
    conclusion['product_name'] = input_data.get('product_name', '未命名商品')
    conclusion['category'] = category
    # 透出关键指标供前端因果分析使用
    conclusion['natural_conv_rate'] = input_data.get('natural_conv_rate')
    conclusion['ad_traffic_ratio'] = input_data.get('ad_traffic_ratio')
    conclusion['cart_fav_visitors'] = input_data.get('cart_fav_visitors')
    conclusion['total_cart'] = input_data.get('total_cart')
    
    # V2.0: 传递维度评分和分层结果供前端渲染
    conclusion['dim_results'] = result.get('dim_results', {})
    conclusion['layer_results'] = result.get('layer_results', {})
    
    return conclusion


def main():
    if len(sys.argv) < 2:
        print(json.dumps({'error': '请提供JSON数据', 'usage': 'python run_diagnosis.py \'{"daily_visitors": 2410, ...}\''}, ensure_ascii=False))
        sys.exit(1)
    
    try:
        input_data = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(json.dumps({'error': f'JSON解析失败: {str(e)}'}, ensure_ascii=False))
        sys.exit(1)
    
    try:
        result = run_diagnosis(input_data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({'error': f'诊断引擎运行失败: {str(e)}'}, ensure_ascii=False))
        sys.exit(1)


if __name__ == '__main__':
    main()
