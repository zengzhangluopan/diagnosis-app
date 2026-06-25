"""
结论生成器 - 把引擎分数翻译成"12年老运营"的自然语言
版本: V3.0 (V6引擎配套)
更新: 2026-06-10

V3.0 变更（基于CG104实战深度升级）:
  1. 推广深度分析：整合推广报表数据，拉新/收割分层评价
  2. 归因修正：剥离自然流量转化金额，真实ROI才是决策依据
  3. 成本维度：无成本数据不下"砍不砍"结论，率低成本低=蓄水
  4. 退款/秒退分析：区分产品问题vs流量不精准
  5. 成交新客占比正确解读：不用于判断是否在拉新
  6. 数据卡片分两层：链接质量指标 + 生意指标

输入: DiagnosisEngine.run() 的结果 + 可选推广诊断数据
输出: 详细的诊断结论（一句结论 + 3个动作 + 关键数据卡片 + 深看提示）
"""

from typing import Optional


# ============================================================
# 一、品类行业基准数据
# ============================================================

CATEGORY_BENCHMARKS = {
    # 行业基准统一用"搜索转化率"口径（这才是链接真实水平）
    # 三档：不及格线 / 同行平均 / 优秀水平
    '净水壶': {
        'name': '净水壶/净水器',
        # 搜索转化率基准
        'search_conv_fail': 1.5,    # 低于此=链接有明显问题
        'search_conv_avg': 3.0,     # 同行平均
        'search_conv_excellent': 4.5, # 头部竞品
        'search_conv_range': '3-4.5%',
        # 整体转化率（仅供参考，被广告稀释）
        'overall_conv_range': '1.5-3%',
        'cart_range': '5-8%',
        'cart_fail': 3.0, 'cart_avg': 6.0, 'cart_excellent': 8.0,
        'bounce_range': '45-60%',
        'bounce_fail': 65, 'bounce_avg': 50, 'bounce_excellent': 40,
        'ad_roi_range': '3-5',
        'ad_roi_fail': 2.0, 'ad_roi_avg': 3.5, 'ad_roi_excellent': 5.0,
        'ctr_range': '2.5-4%',
    },
    '净水器': {
        'name': '净水壶/净水器',
        'search_conv_fail': 1.5,
        'search_conv_avg': 3.0,
        'search_conv_excellent': 4.5,
        'search_conv_range': '3-4.5%',
        'overall_conv_range': '1.5-3%',
        'cart_range': '5-8%',
        'cart_fail': 3.0, 'cart_avg': 6.0, 'cart_excellent': 8.0,
        'bounce_range': '45-60%',
        'bounce_fail': 65, 'bounce_avg': 50, 'bounce_excellent': 40,
        'ad_roi_range': '3-5',
        'ad_roi_fail': 2.0, 'ad_roi_avg': 3.5, 'ad_roi_excellent': 5.0,
        'ctr_range': '2.5-4%',
    },
    '女装': {
        'name': '女装',
        'search_conv_fail': 2.0,
        'search_conv_avg': 4.0,
        'search_conv_excellent': 6.0,
        'search_conv_range': '4-6%',
        'overall_conv_range': '2-3.5%',
        'cart_range': '8-15%',
        'cart_fail': 5.0, 'cart_avg': 10.0, 'cart_excellent': 15.0,
        'bounce_range': '40-55%',
        'bounce_fail': 55, 'bounce_avg': 45, 'bounce_excellent': 35,
        'ad_roi_range': '2-4',
        'ad_roi_fail': 1.5, 'ad_roi_avg': 3.0, 'ad_roi_excellent': 4.0,
        'ctr_range': '3-5%',
    },
    '食品': {
        'name': '食品',
        'search_conv_fail': 3.0,
        'search_conv_avg': 6.0,
        'search_conv_excellent': 10.0,
        'search_conv_range': '6-10%',
        'overall_conv_range': '3-6%',
        'cart_range': '6-12%',
        'cart_fail': 4.0, 'cart_avg': 8.0, 'cart_excellent': 12.0,
        'bounce_range': '35-50%',
        'bounce_fail': 50, 'bounce_avg': 40, 'bounce_excellent': 30,
        'ad_roi_range': '3-6',
        'ad_roi_fail': 2.0, 'ad_roi_avg': 4.0, 'ad_roi_excellent': 6.0,
        'ctr_range': '2-4%',
    },
    '3C数码': {
        'name': '3C数码',
        'search_conv_fail': 1.2,
        'search_conv_avg': 2.5,
        'search_conv_excellent': 4.0,
        'search_conv_range': '2.5-4%',
        'overall_conv_range': '1-2.5%',
        'cart_range': '6-10%',
        'cart_fail': 4.0, 'cart_avg': 7.0, 'cart_excellent': 10.0,
        'bounce_range': '50-65%',
        'bounce_fail': 65, 'bounce_avg': 55, 'bounce_excellent': 45,
        'ad_roi_range': '2-4',
        'ad_roi_fail': 1.5, 'ad_roi_avg': 2.5, 'ad_roi_excellent': 4.0,
        'ctr_range': '1.5-3%',
    },
    '美妆': {
        'name': '美妆',
        'search_conv_fail': 2.5,
        'search_conv_avg': 4.5,
        'search_conv_excellent': 7.0,
        'search_conv_range': '4.5-7%',
        'overall_conv_range': '2-4%',
        'cart_range': '8-12%',
        'cart_fail': 5.0, 'cart_avg': 9.0, 'cart_excellent': 13.0,
        'bounce_range': '40-55%',
        'bounce_fail': 55, 'bounce_avg': 45, 'bounce_excellent': 35,
        'ad_roi_range': '2-4',
        'ad_roi_fail': 1.5, 'ad_roi_avg': 2.5, 'ad_roi_excellent': 4.0,
        'ctr_range': '2.5-4%',
    },
    '家居日用': {
        'name': '家居日用',
        'search_conv_fail': 1.5,
        'search_conv_avg': 3.0,
        'search_conv_excellent': 5.0,
        'search_conv_range': '3-5%',
        'overall_conv_range': '1.5-3.5%',
        'cart_range': '5-8%',
        'cart_fail': 3.0, 'cart_avg': 6.0, 'cart_excellent': 9.0,
        'bounce_range': '45-60%',
        'bounce_fail': 60, 'bounce_avg': 50, 'bounce_excellent': 40,
        'ad_roi_range': '2-4',
        'ad_roi_fail': 1.5, 'ad_roi_avg': 2.5, 'ad_roi_excellent': 4.0,
        'ctr_range': '2-3.5%',
    },
    '母婴': {
        'name': '母婴',
        'search_conv_fail': 2.0,
        'search_conv_avg': 4.0,
        'search_conv_excellent': 6.0,
        'search_conv_range': '4-6%',
        'overall_conv_range': '2-4%',
        'cart_range': '6-10%',
        'cart_fail': 4.0, 'cart_avg': 7.0, 'cart_excellent': 11.0,
        'bounce_range': '40-55%',
        'bounce_fail': 55, 'bounce_avg': 45, 'bounce_excellent': 35,
        'ad_roi_range': '2-4',
        'ad_roi_fail': 1.5, 'ad_roi_avg': 2.5, 'ad_roi_excellent': 4.0,
        'ctr_range': '2-4%',
    },
}

DEFAULT_BENCHMARK = {
    'name': '该品类',
    'search_conv_fail': 1.5,
    'search_conv_avg': 3.0,
    'search_conv_excellent': 4.5,
    'search_conv_range': '3-4.5%',
    'overall_conv_range': '1.5-3%',
    'cart_range': '6-8%',
    'cart_fail': 3.0, 'cart_avg': 6.0, 'cart_excellent': 8.0,
    'bounce_range': '50-55%',
    'bounce_fail': 60, 'bounce_avg': 50, 'bounce_excellent': 40,
    'ad_roi_range': '2-4',
    'ad_roi_fail': 2.0, 'ad_roi_avg': 3.0, 'ad_roi_excellent': 4.0,
    'ctr_range': '2-3%',
}


# ============================================================
# 二、场景判断与结论生成
# ============================================================

def _safe_float(val, default=None):
    """安全转float"""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _judge_ad_value(ctx: dict) -> str:
    """判断广告流量的真实价值
    
    核心逻辑：广告转化率低≠广告该砍
    - 如果CPC足够低，低转化也可以接受（算下单成本）
    - 如果广告带来大量加购，加购后续会转化
    - 只有"转化低+CPC高+加购也少"才是真浪费
    """
    ad_conv = _safe_float(ctx.get('ad_conv_rate'))
    cpc = _safe_float(ctx.get('cpc'))
    ad_cart_rate = _safe_float(ctx.get('ad_cart_rate'))
    ad_roi = _safe_float(ctx.get('ad_roi'))
    conv_rate = _safe_float(ctx.get('conv_rate'))
    ad_ratio = _safe_float(ctx.get('ad_ratio') or ctx.get('ad_traffic_ratio'), 0)
    
    # 如果没有广告转化率，无法判断
    if ad_conv is None:
        return 'unknown'
    
    # 广告转化率不低，广告没问题
    if ad_conv >= 1.5:
        return 'ok'
    
    # 广告转化率低，但需要进一步判断
    if ad_conv < 1.0:
        # 情况1：CPC低 → 单笔订单成本可控，广告有性价比
        if cpc is not None and cpc <= 0.5:
            # CPC ≤ 0.5元，即使0.2%转化，单笔订单成本 = 0.5/0.002 = 250元
            # 对于客单价300+的品类，这可能是可接受的
            price = _safe_float(ctx.get('price'), 200)
            cost_per_order = cpc / (ad_conv / 100)
            if cost_per_order < price * 0.3:  # 订单成本<客单价30%
                return 'low_conv_cheap_cpc'  # 转化低但便宜
        
        # 情况2：加购率高 → 广告在蓄水，不能砍
        if ad_cart_rate is not None and ad_cart_rate >= 5.0:
            return 'low_conv_high_cart'  # 转化低但加购高
        
        # 情况3：ROI还行 → 别急着砍
        if ad_roi is not None and ad_roi >= 2.0:
            return 'low_conv_ok_roi'  # 转化低但ROI可接受
        
        # 情况4：真浪费 — 转化低+没加购+CPC不低
        return 'waste'  # 广告确实在烧钱
    
    # 广告转化率在1.0-1.5之间，中等偏弱
    return 'weak'


def _judge_scenario(ctx: dict, dims: dict) -> str:
    """判断核心场景，决定结论方向
    
    核心原则：
    - 链接真实水平看搜索转化率，整体转化率是生意结果（被广告稀释）
    - 跳失率同样受流量精准度影响，广告占比高时跳失率说明不了页面问题
    - 搜索转化率OK + 整体转化低 = 广告拖累
    - 搜索转化率也差 = 页面/产品有问题
    """
    ad_ratio = _safe_float(ctx.get('ad_ratio') or ctx.get('ad_traffic_ratio'), 0)
    ad_conv = _safe_float(ctx.get('ad_conv_rate'))
    natural_conv = _safe_float(ctx.get('natural_conv_rate'))
    conv_rate = _safe_float(ctx.get('conv_rate'))
    bounce_rate = _safe_float(ctx.get('bounce_rate'))
    monthly_sales = _safe_float(ctx.get('monthly_sales'))
    
    ad_value = _judge_ad_value(ctx)
    
    # 用搜索转化率判断链接真实水平（不是整体转化率）
    real_conv = natural_conv if natural_conv is not None else conv_rate
    
    # ---- 广告占比高的场景 ----
    if ad_ratio > 0.7:
        # 广告确实在烧钱（转化低+加购少+成本高）
        if ad_value == 'waste':
            return 'ad_waste'
        
        # 广告转化低但有加购贡献（蓄水中）
        if ad_value in ('low_conv_high_cart', 'low_conv_cheap_cpc', 'low_conv_ok_roi'):
            return 'ad_low_conv_but_valuable'
        
        # 搜索转化OK但整体低 → 广告拖累
        if natural_conv is not None and natural_conv >= 2.0:
            return 'ad_low_conv_vs_natural'
        
        # 搜索转化也差 → 页面+广告都有问题
        if real_conv is not None and real_conv < 2.0:
            return 'page_issue_with_ad'
    
    # ---- 广告占比不高的场景 ----
    # 搜索转化率差 → 页面/产品有问题
    if real_conv is not None and real_conv < 2.0:
        return 'page_issue'
    
    # 销量基数太小
    if monthly_sales is not None and monthly_sales < 30:
        return 'sales_base_low'
    
    return 'general'


def _generate_one_liner(ctx: dict, dims: dict, scenario: str, benchmark: dict) -> str:
    """生成一句话结论——带具体数字+行业对比+逻辑推导"""
    
    ad_ratio = _safe_float(ctx.get('ad_ratio') or ctx.get('ad_traffic_ratio'), 0)
    ad_conv = ctx.get('ad_conv_rate') or '?'
    natural_conv = ctx.get('natural_conv_rate') or '?'
    conv_rate = ctx.get('conv_rate') or '?'
    bounce_rate = ctx.get('bounce_rate') or '?'
    cpc = ctx.get('cpc')
    ad_cart_rate = ctx.get('ad_cart_rate')
    
    if scenario == 'ad_waste':
        parts = [f'核心问题是广告流量极度不精准']
        parts.append(f'广告转化率仅{ad_conv}%拉低了整体转化')
        natural_val = _safe_float(natural_conv)
        if natural_val and natural_val > 2.0:
            parts.append(f'而自然搜索{natural_conv}%的转化率证明页面产品力没问题')
        parts.append('之前的广告就是撒网式投流，逮着谁算谁，完全不看精准度😤')
        return '，'.join(parts)
    
    elif scenario == 'ad_low_conv_but_valuable':
        ad_value = _judge_ad_value(ctx)
        parts = [f'广告转化率{ad_conv}%确实偏低']
        
        if ad_value == 'low_conv_high_cart':
            parts.append(f'但广告加购率达到{ad_cart_rate}%，说明广告在蓄水——用户感兴趣但还没下单，别急着砍')
        elif ad_value == 'low_conv_cheap_cpc':
            cpc_val = _safe_float(cpc, 0)
            ad_conv_val = _safe_float(ad_conv, 0.2)
            if cpc_val > 0 and ad_conv_val > 0:
                cost_per_order = cpc_val / (ad_conv_val / 100)
                parts.append(f'但CPC只要{cpc}元，算下来单笔订单成本约{cost_per_order:.0f}元，性价比还行')
            else:
                parts.append(f'但CPC很低，广告成本可控')
        elif ad_value == 'low_conv_ok_roi':
            parts.append('但广告ROI还能接受，说明广告整体是有产出的')
        
        natural_val = _safe_float(natural_conv)
        if natural_val and natural_val > 2.0:
            parts.append(f'自然搜索转化{natural_conv}%证明产品没问题')
        parts.append('关键是把广告的精准度提上去，而不是简单砍掉')
        return '，'.join(parts)
    
    elif scenario == 'ad_low_conv_vs_natural':
        parts = [f'广告转化率{ad_conv}%远低于自然搜索{natural_conv}%']
        parts.append(f'{int(ad_ratio*100)}%的流量来自付费，但付费流量质量差，拖累了整体数据')
        parts.append('页面产品力没问题，问题在广告人群不够精准')
        return '——'.join(parts)
    
    elif scenario == 'page_issue':
        real_conv_val = natural_conv if natural_conv != '?' and _safe_float(natural_conv) else conv_rate
        return f'别怪广告了——搜索转化率才{real_conv_val}%，同行平均{benchmark["search_conv_range"]}，用户主动搜进来了都不买，页面和产品本身就有问题'
    
    elif scenario == 'page_issue_with_ad':
        real_conv_val = natural_conv if natural_conv != '?' and _safe_float(natural_conv) else conv_rate
        return f'两个问题都有——搜索转化率{real_conv_val}%低于同行平均{benchmark["search_conv_range"]}，页面产品力不行；同时广告也不精准，双重拖累'
    
    elif scenario == 'sales_base_low':
        monthly_sales = ctx.get('monthly_sales', '?')
        return f'月销{monthly_sales}件，连品类前50都进不去，自然流量飞轮根本没转起来，先拉销量基数再说别的'
    
    else:
        scored = [(did, dr) for did, dr in dims.items() if dr.get('score') is not None]
        if scored:
            severity = sorted(scored, key=lambda x: x[1]['weight'] * (10 - x[1]['score']), reverse=True)
            top_did, top_dr = severity[0]
            dim_name = top_dr.get('name', top_did)
            score = top_dr.get('score', 5)
            return f'{dim_name}得分偏低（{score}/10），是目前最需要优化的方向'
        return '数据不足，无法生成准确结论'


def _generate_actions(ctx: dict, dims: dict, scenario: str, benchmark: dict) -> list:
    """生成三个动作——具体到操作步骤"""
    
    ad_ratio = _safe_float(ctx.get('ad_ratio') or ctx.get('ad_traffic_ratio'), 0)
    ad_conv = _safe_float(ctx.get('ad_conv_rate'))
    natural_conv = _safe_float(ctx.get('natural_conv_rate'))
    conv_rate = _safe_float(ctx.get('conv_rate'))
    cpc = _safe_float(ctx.get('cpc'))
    ad_cart_rate = _safe_float(ctx.get('ad_cart_rate'))
    ad_roi = _safe_float(ctx.get('ad_roi'))
    category = ctx.get('category', '该品类')
    price = _safe_float(ctx.get('price'))
    
    actions = []
    
    if scenario == 'ad_waste':
        # 🔴 砍低效广告定向（但要说清判断标准）
        actions.append({
            'priority': 'urgent',
            'title': '砍掉"转化低+加购低+成本高"的广告定向',
            'what': '打开直通车/引力魔方后台，导出近7天所有定向和关键词数据，按"转化率×加购率/CPC"排序，砍掉三项都差的（转化<0.3%且加购<3%且CPC>行业均值）',
            'why': f'现在{int(ad_ratio*100)}%的流量是付费，其中一部分确实是无效点击，先止损——但注意，如果某个定向转化低但加购率高，不要砍，那是蓄水流量',
            'expected': '砍掉真浪费的预算，省下的钱加到高转化/高加购的定向上',
        })
        
        # 🟡 用自然搜索高转化词投广告
        if natural_conv and natural_conv > 2.0:
            actions.append({
                'priority': 'important',
                'title': '把自然搜索TOP10高转化词加到广告精准匹配',
                'what': '打开生意参谋→流量→搜索词排行，导出近7天自然搜索TOP10的词，加到直通车精准匹配计划里',
                'why': f'自然搜索转化率{natural_conv}%，说明这些词的用户是真正想买{category}的人，用这些词投广告能匹配到精准需求',
                'expected': f'广告转化率能拉到2%以上，逐步接近自然搜索{natural_conv}%的水平',
            })
        else:
            actions.append({
                'priority': 'important',
                'title': '从"兴趣人群"缩到"搜索+加购人群"',
                'what': '广告人群包从大范围兴趣定向，缩小到"近7天搜索过品类词+加购未购买"的人群，出价提高20%-30%',
                'why': '兴趣人群太泛，搜索+加购人群才是有明确购买意图的人',
                'expected': '广告转化率提升50%-100%，点击量可能下降但有效点击增加',
            })
        
        # 🟢 用高转化卖点优化广告创意
        actions.append({
            'priority': 'normal',
            'title': '用高转化卖点优化广告创意',
            'what': '把详情页里用户最关心的核心卖点放到广告主图和创意标题里',
            'why': '现在广告创意可能没筛选掉无效用户，用精准卖点能减少非目标用户的点击，提升广告质量分',
            'expected': '广告点击率提升1%-2%，进一步降低单次点击成本',
        })
    
    elif scenario == 'ad_low_conv_but_valuable':
        ad_value = _judge_ad_value(ctx)
        
        # 🔴 提升广告精准度（不是砍，是优化）
        if ad_value == 'low_conv_high_cart':
            actions.append({
                'priority': 'urgent',
                'title': '把高加购定向的预算加大，低加购的砍掉',
                'what': '导出广告各定向的加购率数据，加购率>5%的加预算30%-50%，加购率<2%且转化<0.3%的暂停——让广告从"泛投蓄水"变成"精准蓄水"',
                'why': f'广告加购率{ad_cart_rate}%说明广告确实在带来潜在客户，但部分定向的加购太低是纯浪费，把预算集中到有效的定向上',
                'expected': '同样预算下加购量提升30%+，后续转化自然上来',
            })
        elif ad_value == 'low_conv_cheap_cpc':
            cpc_val = cpc or '?'
            ad_conv_val = ad_conv or 0.2
            cost_str = ''
            if cpc and ad_conv_val > 0:
                cost_per_order = cpc / (ad_conv_val / 100)
                cost_str = f'（当前单笔订单成本约{cost_per_order:.0f}元）'
            actions.append({
                'priority': 'urgent',
                'title': 'CPC低是优势，但要提升转化率把成本进一步打下来',
                'what': f'保持当前低CPC的广告位，同时优化广告创意和人群定向——创意加核心卖点筛选无效点击，人群从泛兴趣缩到搜索+加购{cost_str}',
                'why': f'CPC{cpc_val}元确实便宜，但转化率{ad_conv}%偏低意味着每1000次点击才{ad_conv_val*10:.0f}单，提升转化空间很大',
                'expected': '转化率翻倍的话，单笔订单成本直接砍半',
            })
        else:
            actions.append({
                'priority': 'urgent',
                'title': '优化广告精准度，别急着砍',
                'what': '分析各广告定向的转化率和加购率，砍掉转化+加购都差的，把省下的预算加到表现好的定向上',
                'why': '广告ROI还能接受，说明整体方向没错，但精准度需要提升',
                'expected': '同样预算下产出提升20%-30%',
            })
        
        # 🟡 用自然搜索词优化广告
        if natural_conv and natural_conv > 2.0:
            actions.append({
                'priority': 'important',
                'title': '把自然搜索TOP10高转化词加到广告精准匹配',
                'what': '打开生意参谋→流量→搜索词排行，导出近7天自然搜索TOP10的词，加到直通车精准匹配计划里',
                'why': f'自然搜索转化{natural_conv}%远高于广告{ad_conv}%，用这些词投广告能直接拉高广告转化',
                'expected': f'广告转化率从{ad_conv}%拉到2%以上',
            })
        
        # 🟢 做加购转化（把蓄水流量变成成交）
        actions.append({
            'priority': 'normal',
            'title': '做加购未购买的追回',
            'what': '设置购物车营销（限时优惠/加购专享价），对7天内加购未购买的用户做二次触达',
            'why': '广告带来大量加购但没转化，说明用户在犹豫——给个临门一脚的优惠就能转化',
            'expected': '加购转化率提升5-10个百分点',
        })
    
    elif scenario == 'ad_low_conv_vs_natural':
        actions.append({
            'priority': 'urgent',
            'title': '分析广告各定向数据，区分"蓄水"和"浪费"',
            'what': '导出近7天广告各定向的转化率+加购率+CPC，三类分别标记：①转化>1%或加购>5%=优质保留 ②转化0.3%-1%且加购3%-5%=蓄水观察 ③转化<0.3%且加购<3%=纯浪费砍掉',
            'why': f'广告转化{ad_conv}%远低于自然搜索{natural_conv}%，说明大部分广告人群不对，但可能有部分定向是好的，不能一刀切',
            'expected': '砍掉纯浪费部分（通常占20%-30%预算），加到优质定向上',
        })
        actions.append({
            'priority': 'important',
            'title': '把自然搜索TOP10高转化词加到广告精准匹配',
            'what': '打开生意参谋→流量→搜索词排行，导出近7天自然搜索TOP10的词，加到直通车精准匹配计划里',
            'why': f'自然搜索转化{natural_conv}%，这些词的用户是精准人群，用这些词投广告效果最好',
            'expected': f'广告转化率逐步拉到{natural_conv}%的60%-80%',
        })
        actions.append({
            'priority': 'normal',
            'title': '用高转化卖点优化广告创意',
            'what': '把详情页里用户最关心的核心卖点放到广告主图和创意标题里',
            'why': '创意是筛选用户的第一道关，精准卖点是天然的漏斗',
            'expected': '广告点击率提升1%-2%，降低无效点击',
        })
    
    elif scenario == 'page_issue':
        actions.append({
            'priority': 'urgent',
            'title': '详情页首屏3秒测试——能不能让用户立刻知道"这产品对我有什么好处"',
            'what': '用手机打开自己的详情页，3秒后截屏——如果首屏没有核心卖点、没有信任背书、没有使用场景，就得重做',
            'why': f'搜索转化率才{natural_conv or conv_rate}%，用户主动搜进来都不买，说明页面没说服力',
            'expected': '首屏重做后搜索转化率提升30%-50%',
        })
        actions.append({
            'priority': 'important',
            'title': '按用户决策逻辑重排详情页五层',
            'what': '一屏：最大卖点 → 二屏：信任背书（检测报告/用户证言） → 三屏：竞品对比优势 → 四屏：使用场景 → 五屏：消除顾虑（售后/评价）',
            'why': '现在页面信息可能都有，但没按用户决策顺序排，用户找不到想看的就走了',
            'expected': '页面停留时长提升30%+，加购率提升',
        })
        actions.append({
            'priority': 'normal',
            'title': '做3版主图A/B测试',
            'what': '设计3张不同角度的主图：卖点型/场景型/对比型，每张测2000展现',
            'why': '点击率决定了所有后续流量的基数，主图不行后面都白搭',
            'expected': '找到最优主图后点击率提升20%-30%',
        })
    
    elif scenario == 'page_issue_with_ad':
        real_conv_val = natural_conv or conv_rate or '?'
        # 两个问题都有，优先修页面（搜索转化低是根本问题）
        actions.append({
            'priority': 'urgent',
            'title': '先修页面——搜索转化率{val}%说明用户来了也不买'.format(val=real_conv_val),
            'what': '用手机打开详情页首屏3秒测试：有没有核心卖点？有没有信任背书？如果没有就得重做。同时检查差评和问大家的Top5问题',
            'why': f'搜索转化{real_conv_val}%远低于同行平均{benchmark["search_conv_range"]}，这是根本问题——页面不修好，广告再精准也白搭',
            'expected': '搜索转化率提升到同行平均线',
        })
        actions.append({
            'priority': 'important',
            'title': '同步优化广告精准度',
            'what': '导出广告各定向的转化率+加购率，砍掉转化+加购都差的，把预算加到高转化/高加购的定向上',
            'why': f'广告占比{int(ad_ratio*100)}%但搜索转化也低，说明广告人群和页面都不行，两边都要改',
            'expected': '广告ROI提升50%+，搜索转化率同步提升',
        })
        actions.append({
            'priority': 'normal',
            'title': '强化差异化卖点',
            'what': '找到竞品没做/做得差的1-2个点，在主图+标题+详情页反复强化',
            'why': '搜索转化低很多时候是用户分不清你和竞品的区别',
            'expected': '减少同质化竞争，搜索转化回升',
        })
    
    elif scenario == 'sales_base_low':
        actions.append({
            'priority': 'urgent',
            'title': '短期拉销量基数——精准广告+促销组合',
            'what': '选定1-2个核心SKU，用精准搜索词投广告，配合限时优惠/满减，目标2周内月销翻倍',
            'why': f'月销{ctx.get("monthly_sales", "?")}件太低，自然流量飞轮没转起来，需要推一把突破临界点',
            'expected': '月销突破品类前50后，自然搜索流量会明显增长',
        })
        actions.append({
            'priority': 'important',
            'title': '补搜索词覆盖',
            'what': '从生意参谋导出品类TOP50搜索词，逐个检查标题和直通车有没有覆盖，缺的补上',
            'why': '月销低的链接通常搜索词覆盖率也很低，大量免费流量被竞品吃掉了',
            'expected': '自然搜索流量提升30%-50%',
        })
        actions.append({
            'priority': 'normal',
            'title': '考虑参加平台活动冲量',
            'what': '报名聚划算/百亿补贴/品类日等平台活动，用低价换销量，目标是快速拉起月销基数',
            'why': '靠日常运营拉量太慢，活动流量能在短期内冲起来',
            'expected': '活动期间月销翻3-5倍，活动后保留部分自然流量',
        })
    
    else:
        # 通用场景：按维度严重度排序
        scored = [(did, dr) for did, dr in dims.items() if dr.get('score') is not None]
        severity = sorted(scored, key=lambda x: x[1]['weight'] * (10 - x[1]['score']), reverse=True)
        
        priority_count = {'urgent': 0, 'important': 0, 'normal': 0}
        for dim_id, dr in severity[:3]:
            score = dr.get('score', 5)
            dim_name = dr.get('name', dim_id)
            
            if score <= 3:
                p = 'urgent'
            elif score <= 5:
                p = 'important'
            else:
                p = 'normal'
            
            if priority_count['urgent'] > 0 and p == 'urgent':
                p = 'important'
            if priority_count['urgent'] + priority_count['important'] >= 2 and p == 'important':
                p = 'normal'
            
            actions.append({
                'priority': p,
                'title': f'优化{dim_name}',
                'what': f'针对{dim_name}得分({score}/10)进行专项优化',
                'why': f'{dim_name}是当前短板，影响整体表现',
                'expected': f'{dim_name}改善后带动整体转化提升',
            })
            priority_count[p] += 1
    
    return actions[:3]


def _generate_data_card(ctx: dict, benchmark: dict) -> list:
    """生成关键数据卡片——区分生意指标和链接质量指标"""
    items = []
    sources = ctx.get('data_sources', {})
    SRC_TAG = {'user': '✅', 'default': '⚠️'}
    
    def tag(key):
        s = sources.get(key, 'default')
        return SRC_TAG.get(s, '⚠️')
    
    # ---- 链接质量指标（看真实水平） ----
    items.append('📊 链接质量指标')
    
    if ctx.get('natural_conv_rate'):
        nat_conv = ctx['natural_conv_rate']
        nat_val = _safe_float(nat_conv)
        if nat_val is not None:
            if nat_val < benchmark['search_conv_fail']:
                items.append(f'{tag("natural_conv_rate")} 搜索转化率：{nat_conv}%（低于及格线{benchmark["search_conv_fail"]}% 🔴）')
            elif nat_val < benchmark['search_conv_avg']:
                items.append(f'{tag("natural_conv_rate")} 搜索转化率：{nat_conv}%（同行平均{benchmark["search_conv_avg"]}%，还有提升空间 🟡）')
            elif nat_val < benchmark['search_conv_excellent']:
                items.append(f'{tag("natural_conv_rate")} 搜索转化率：{nat_conv}%（高于同行平均，接近优秀 👍）')
            else:
                items.append(f'{tag("natural_conv_rate")} 搜索转化率：{nat_conv}%（优秀水平 🟢）')
        else:
            items.append(f'{tag("natural_conv_rate")} 搜索转化率：{nat_conv}%')
    
    if ctx.get('ad_conv_rate'):
        items.append(f'{tag("ad_conv_rate")} 广告转化率：{ctx["ad_conv_rate"]}%')
    
    if ctx.get('ad_cart_rate'):
        cart_val = _safe_float(ctx['ad_cart_rate'])
        if cart_val is not None:
            if cart_val >= benchmark['cart_excellent']:
                items.append(f'{tag("ad_cart_rate")} 广告加购率：{ctx["ad_cart_rate"]}%（优秀 🟢）')
            elif cart_val >= benchmark['cart_avg']:
                items.append(f'{tag("ad_cart_rate")} 广告加购率：{ctx["ad_cart_rate"]}%（同行平均{benchmark["cart_avg"]}%）')
            else:
                items.append(f'{tag("ad_cart_rate")} 广告加购率：{ctx["ad_cart_rate"]}%（偏低 🔴）')
        else:
            items.append(f'{tag("ad_cart_rate")} 广告加购率：{ctx["ad_cart_rate"]}%')
    
    # ---- 生意指标（看结果，受流量结构影响） ----
    items.append('📈 生意指标（受流量结构影响）')
    
    if ctx.get('daily_visitors'):
        items.append(f'{tag("daily_visitors")} 日均访客数：{ctx["daily_visitors"]:,}')
    
    if ctx.get('ad_ratio') or ctx.get('ad_traffic_ratio'):
        ratio = ctx.get('ad_ratio') or ctx.get('ad_traffic_ratio')
        if isinstance(ratio, float) and ratio < 1:
            ratio = f'{int(ratio*100)}%'
        items.append(f'{tag("ad_ratio")} 广告流量占比：{ratio}')
    
    if ctx.get('conv_rate'):
        conv = ctx['conv_rate']
        items.append(f'{tag("conv_rate")} 整体转化率：{conv}%（参考：行业整体{benchmark["overall_conv_range"]}）')
    
    if ctx.get('cpc'):
        items.append(f'{tag("cpc")} 广告CPC：{ctx["cpc"]}元')
    
    if ctx.get('ad_roi'):
        roi_val = _safe_float(ctx['ad_roi'])
        if roi_val is not None:
            if roi_val < benchmark['ad_roi_fail']:
                items.append(f'{tag("ad_roi")} 广告ROI：{ctx["ad_roi"]}（低于及格线{benchmark["ad_roi_fail"]} 🔴）')
            elif roi_val >= benchmark['ad_roi_excellent']:
                items.append(f'{tag("ad_roi")} 广告ROI：{ctx["ad_roi"]}（优秀 🟢）')
            else:
                items.append(f'{tag("ad_roi")} 广告ROI：{ctx["ad_roi"]}（同行平均{benchmark["ad_roi_avg"]}）')
        else:
            items.append(f'{tag("ad_roi")} 广告ROI：{ctx["ad_roi"]}')
    
    if ctx.get('price'):
        items.append(f'{tag("price")} 客单价：{ctx["price"]}元')
    
    if ctx.get('monthly_sales'):
        items.append(f'{tag("monthly_sales")} 月销：{ctx["monthly_sales"]}件')
    
    if ctx.get('bounce_rate'):
        bounce = ctx['bounce_rate']
        ad_ratio_val = _safe_float(ctx.get('ad_ratio') or ctx.get('ad_traffic_ratio'), 0)
        if ad_ratio_val > 0.7:
            items.append(f'{tag("bounce_rate")} 跳失率：{bounce}%（广告占比高，此指标受流量精准度影响，不反映页面质量）')
        elif ad_ratio_val > 0.5:
            items.append(f'{tag("bounce_rate")} 跳失率：{bounce}%（广告占比较高，此指标部分受流量影响）')
        else:
            items.append(f'{tag("bounce_rate")} 跳失率：{bounce}%')
    
    # 行业基准
    items.append('---')
    items.append(f'⚠️ 同行基准（搜索转化）：不及格<{benchmark["search_conv_fail"]}% / 平均{benchmark["search_conv_avg"]}% / 优秀{benchmark["search_conv_excellent"]}%+')
    items.append('⚠️ = 行业默认值（非实际数据），提供实际数据结论更准')
    
    return items


def _generate_deep_dive(ctx: dict, dims: dict, scenario: str) -> list:
    """生成深看提示——带初步分析"""
    hints = []
    
    ad_ratio = _safe_float(ctx.get('ad_ratio') or ctx.get('ad_traffic_ratio'), 0)
    ad_conv = ctx.get('ad_conv_rate')
    natural_conv = ctx.get('natural_conv_rate')
    conv_rate = ctx.get('conv_rate')
    bounce_rate = ctx.get('bounce_rate')
    
    if scenario in ('ad_waste', 'ad_low_conv_but_valuable', 'ad_low_conv_vs_natural'):
        if bounce_rate and ad_conv and natural_conv:
            ad_ratio_pct = int(ad_ratio * 100)
            real_bounce = int(float(bounce_rate) * (1 - ad_ratio * 0.6))
            hints.append({
                'question': f'为什么跳失率{bounce_rate}%不是页面问题？',
                'preview': f'广告转化{ad_conv}% vs 自然搜索转化{natural_conv}%——{ad_ratio_pct}%的流量来自广告，这批人本来就没打算买，跳走是正常的。去掉广告流量的干扰，真实跳失率大约{real_bounce}%，在行业正常范围内',
            })
        
        hints.append({
            'question': '广告具体怎么优化？哪些该砍哪些该加？',
            'preview': '不能一刀切——导出各定向的转化率+加购率+CPC，分三类处理：①转化>1%或加购>5%=加预算 ②转化0.3%-1%=观察优化 ③转化<0.3%且加购<3%=砍掉。砍完预算移到优质定向上',
        })
        
        hints.append({
            'question': '搜索词覆盖率怎么查、怎么补？',
            'preview': '生意参谋→流量→搜索词排行→导出近7天TOP50→逐个检查标题是否包含→直通车是否覆盖→缺的先补标题再开精准匹配',
        })
    
    elif scenario == 'page_issue':
        hints.append({
            'question': '详情页哪里有问题？',
            'preview': f'自然搜索转化{natural_conv}%远低于行业，用户主动搜进来了都不买，问题在：①首屏卖点不清晰 ②信任背书不够 ③价格/性价比没说清楚 ④评价区有硬伤',
        })
        hints.append({
            'question': '怎么重做详情页逻辑？',
            'preview': '五层逻辑：①最大卖点（3秒打动）→ ②信任背书（检测报告/用户证言）→ ③对比优势（和不用/和竞品）→ ④使用场景（生活化）→ ⑤消除顾虑（售后/评价）',
        })
    
    elif scenario == 'product_issue':
        hints.append({
            'question': '为什么说不是流量问题是产品问题？',
            'preview': f'转化率{conv_rate}%——如果是流量问题，自然搜索转化应该正常；如果自然搜索也低，说明产品力不够或者价格定位有问题',
        })
    
    elif scenario == 'detail_page_issue':
        hints.append({
            'question': '跳失率高具体怎么降？',
            'preview': f'跳失率{bounce_rate}%，先排除加载速度问题（手机4G打开>3秒就优化图片），再改首屏内容（3秒内必须看到核心卖点），最后检查价格和评价区',
        })
    
    if not hints:
        scored = [(did, dr) for did, dr in dims.items() if dr.get('score') is not None]
        if scored:
            severity = sorted(scored, key=lambda x: x[1]['weight'] * (10 - x[1]['score']), reverse=True)
            for dim_id, dr in severity[:2]:
                dim_name = dr.get('name', dim_id)
                hints.append({
                    'question': f'{dim_name}详细分析',
                    'preview': f'{dim_name}得分{dr.get("score", "?")}/10，点击展开具体问题和优化建议',
                })
    
    return hints[:4]


# ============================================================
# 三、结论生成器主类
# ============================================================

class ConclusionGenerator:
    """把引擎分数翻译成12年老运营的自然语言 — V3.0 深度版"""

    def __init__(self, engine_result: dict, extra_context: dict = None, ad_diagnosis: dict = None):
        self.result = engine_result
        self.ctx = extra_context or {}
        self.dims = engine_result.get('dim_results', {})
        self.ad_diagnosis = ad_diagnosis  # 推广深度诊断数据（V6新增）
        self.benchmark = CATEGORY_BENCHMARKS.get(
            self.ctx.get('category', ''),
            DEFAULT_BENCHMARK
        )

    def generate(self) -> dict:
        """生成完整的诊断结论"""
        scenario = _judge_scenario(self.ctx, self.dims)
        
        result = {
            'one_liner': _generate_one_liner(self.ctx, self.dims, scenario, self.benchmark),
            'actions': _generate_actions(self.ctx, self.dims, scenario, self.benchmark),
            'data_card': _generate_data_card(self.ctx, self.benchmark),
            'deep_dive_hint': _generate_deep_dive(self.ctx, self.dims, scenario),
            'scenario': scenario,
        }
        
        # V6新增：有推广深度诊断数据时，覆盖/增强结论
        if self.ad_diagnosis and 'error' not in self.ad_diagnosis:
            result['ad_diagnosis'] = self.ad_diagnosis
            result['ad_one_liner'] = self._generate_ad_one_liner()
            result['ad_actions'] = self._generate_ad_actions()
            result['ad_data_card'] = self._generate_ad_data_card()
            # 有推广数据时，主结论也升级
            result['one_liner'] = self._generate_ad_one_liner()
            result['actions'] = self._generate_ad_actions() + result['actions'][:1]
        
        return result

    def _generate_ad_one_liner(self) -> str:
        """基于推广深度数据生成一句话结论"""
        ad = self.ad_diagnosis
        summary = ad.get('summary', {})
        surface_roi = summary.get('surface_roi')
        surface_roi = summary.get('surface_roi')
        inflation = summary.get('roi_inflation', 0)
        refund_impact = ad.get('refund_impact', {})
        
        parts = []
        
        # 核心判断：真实ROI水平（推广ROI不考虑退款，退款是产品/服务维度的问题）
        if surface_roi is not None:
            if surface_roi < 2.0:
                if surface_roi < 1.0:
                    parts.append(f'推广整体亏损（ROI仅{surface_roi}）')
                else:
                    parts.append(f'推广ROI偏低（ROI {surface_roi}），拉新收割都需优化')
            elif surface_roi < 3.0:
                # 用分层ROI判断结构健康度（从ad_diagnosis直接取，不依赖_uv_value）
                _launch_diag = ad.get('launch_diagnosis', {})
                _harvest_diag = ad.get('harvest_diagnosis', {})
                _l_roi = _launch_diag.get('surface_roi') if isinstance(_launch_diag, dict) and _launch_diag.get('status') != 'no_data' else None
                _h_roi = _harvest_diag.get('surface_roi') if isinstance(_harvest_diag, dict) and _harvest_diag.get('status') != 'no_data' else None
                if _l_roi is not None and _h_roi is not None and _l_roi >= 3.0 and _h_roi >= 4.0:
                    parts.append(f'推广ROI中等（ROI {surface_roi}），分层结构健康，可微调')
                elif _l_roi is not None and _h_roi is not None and _l_roi < 2.0 and _h_roi < 3.0:
                    parts.append(f'推广ROI中等（ROI {surface_roi}），拉新收割都需优化')
                elif _l_roi is not None and _l_roi < 2.0:
                    parts.append(f'推广ROI中等（ROI {surface_roi}），拉新ROI偏低需优化')
                elif _h_roi is not None and _h_roi < 3.0:
                    parts.append(f'推广ROI中等（ROI {surface_roi}），收割ROI偏低需优化')
                else:
                    parts.append(f'推广ROI中等（ROI {surface_roi}），分层数据不完整待优化')
            else:
                parts.append(f'推广整体ROI健康（ROI {surface_roi}），但分层结构有问题')
        else:
            parts.append('推广数据不完整，无法计算ROI')
        
        # 退款率提醒（不影响ROI评价，但影响实际净收入）
        refund_rate = refund_impact.get('refund_rate')
        refund_severity = refund_impact.get('severity', 'normal')
        if refund_rate and refund_severity == 'severe':
            refund_cause = refund_impact.get('refund_root_cause', '')
            if refund_cause == 'hybrid_plan_cart_stuffing':
                parts.append(f'退款率{refund_rate}%需关注（全站推广凑单导致，不影响推广效率判断但影响净收入）')
            elif refund_cause == 'traffic_imprecision':
                parts.append(f'退款率{refund_rate}%偏高（流量不精准导致秒退，推广精准度需提升）')
            else:
                parts.append(f'退款率{refund_rate}%偏高，影响净收入')
        
        # 结构问题
        launch = ad.get('launch_diagnosis', {})
        harvest = ad.get('harvest_diagnosis', {})
        waste_plans = harvest.get('waste_plans', [])
        worst_launch = launch.get('worst_plans', [])
        
        if waste_plans:
            waste_names = [p['plan_name'] for p in waste_plans[:2]]
            parts.append(f'{"、".join(waste_names)}效率极低')
        
        if worst_launch:
            worst_names = [p['plan_name'] for p in worst_launch[:2]]
            parts.append(f'{"、".join(worst_names)}蓄水效率低')
        
        best_plan = launch.get('best_cart_plan')
        if best_plan:
            cart_rate = best_plan.get('cart_rate')
            parts.append(f'{best_plan["plan_name"]}蓄水最强{f"（加购率{cart_rate}%）" if cart_rate else ""}，应该加量')
        
        return '；'.join(parts) if parts else '推广数据不足，无法生成深度结论'

    def _generate_ad_actions(self) -> list:
        """基于推广深度数据生成具体动作"""
        ad = self.ad_diagnosis
        raw_actions = ad.get('actions', [])
        
        actions = []
        PRIORITY_MAP = {'urgent': 'urgent', 'important': 'important', 'normal': 'normal'}
        
        for a in raw_actions[:3]:  # 最多3个推广动作
            action_type = a.get('action')
            target = a.get('target', '未命名计划')
            reason = a.get('reason', '')
            
            if action_type == 'kill':
                actions.append({
                    'priority': 'urgent',
                    'title': f'砍掉{target}',
                    'what': f'在无界后台暂停计划「{target}」',
                    'why': reason,
                    'expected': f'每月省¥{a.get("save_cost", "?")}',
                })
            elif action_type == 'reduce_budget':
                save = a.get('save_cost')
                reduce_pct = a.get('reduce_pct')
                actions.append({
                    'priority': 'important',
                    'title': f'减{target}日预算{reduce_pct}%（月省¥{save:.0f}）' if save else f'减{target}日预算{reduce_pct}%',
                    'what': f'在无界后台将「{target}」的日预算下调{reduce_pct}%左右',
                    'why': reason,
                    'expected': f'每月省¥{save:.0f}，挪给蓄水效率更高的计划' if save else '挪给蓄水效率更高的计划',
                })
            elif action_type == 'increase_budget':
                current = a.get('current_cost')
                actions.append({
                    'priority': 'important',
                    'title': f'{target}加量',
                    'what': f'在无界后台将「{target}」的预算提升50%-100%',
                    'why': reason,
                    'expected': '同样预算下蓄水量和成交双提升',
                })
            elif action_type == 'check_audience':
                actions.append({
                    'priority': 'normal',
                    'title': f'检查{target}人群包',
                    'what': f'回无界后台查看「{target}」的人群包圈选范围，确认是"已加购/收藏未购"还是泛化的"相似人群"',
                    'why': reason,
                    'expected': '精准人群包后转化率提升至3%+',
                })
        
        # 如果没有推广动作，生成通用建议
        if not actions:
            actions.append({
                'priority': 'important',
                'title': '导出推广报表做深度分析',
                'what': '在阿里妈妈后台导出近30天推广报表（含花费、成交、加购、自然流量转化等列），上传给我做深度诊断',
                'why': '只有流量转化率数据无法判断"该砍还是该加"，必须结合成本数据才能下结论',
                'expected': '找到真浪费的预算并重新分配',
            })
        
        return actions

    def _generate_ad_data_card(self) -> list:
        """生成推广深度数据卡片"""
        ad = self.ad_diagnosis
        summary = ad.get('summary', {})
        items = []
        
        items.append('💰 推广深度指标')
        
        if summary.get('total_cost'):
            items.append(f'推广总花费：¥{summary["total_cost"]:,.0f}')
        
        if summary.get('surface_roi'):
            items.append(f'ROI：{summary["surface_roi"]}')
        
        # 退款问题（独立于推广ROI）
        refund = ad.get('refund_impact', {})
        if refund.get('refund_rate') and refund.get('severity') == 'severe':
            items.append(f'退款率：{refund["refund_rate"]}%（{refund.get("refund_explanation", "偏高")}）')
        
        # 混合型计划
        hybrid_plans = ad.get('hybrid_plans', [])
        if hybrid_plans:
            for hp in hybrid_plans:
                items.append(f'混合型计划：{hp["plan_name"]}（拉新:收割 = {int(hp.get("launch_ratio", 0.5)*100)}:{int((1-hp.get("launch_ratio", 0.5))*100)}）')
        
        # 拉新层
        launch = ad.get('launch_diagnosis', {})
        if launch.get('total_cost'):
            items.append(f'拉新层花费：¥{launch["total_cost"]:,.0f}（ROI {launch.get("surface_roi", "?")}）')
        
        # 收割层
        harvest = ad.get('harvest_diagnosis', {})
        if harvest.get('total_cost'):
            items.append(f'收割层花费：¥{harvest["total_cost"]:,.0f}（ROI {harvest.get("surface_roi", "?")}）')
        
        # 混合型计划层（全站推广，不拆分）
        hybrid = ad.get('hybrid', {})
        if hybrid.get('cost'):
            items.append(f'全站推广花费：¥{hybrid["cost"]:,.0f}（ROI {hybrid.get("surface_roi", "?")}，拉新收割混合不拆分）')
        
        return items

    def generate_markdown(self) -> str:
        """生成Markdown格式的完整报告"""
        output = self.generate()
        lines = []

        product_name = self.ctx.get('product_name', '你的商品')
        lines.append(f'# 🔍 诊断结论：{product_name}')
        lines.append('')

        lines.append('## 一句话结论')
        lines.append('')
        lines.append(output['one_liner'])
        lines.append('')

        lines.append('## 三个动作（按优先级）')
        lines.append('')
        PRIORITY_ICON = {'urgent': '🔴', 'important': '🟡', 'normal': '🟢'}
        for action in output['actions']:
            icon = PRIORITY_ICON.get(action['priority'], '🟢')
            lines.append(f'{icon} {action["title"]}')
            lines.append(f'  做什么：{action["what"]}')
            lines.append(f'  为什么：{action["why"]}')
            lines.append(f'  预期效果：{action["expected"]}')
            lines.append('')

        lines.append('## 关键数据')
        lines.append('')
        for item in output['data_card']:
            lines.append(f'- {item}')
        lines.append('')

        if output['deep_dive_hint']:
            lines.append('## 想深看？')
            lines.append('')
            for hint in output['deep_dive_hint']:
                if isinstance(hint, dict):
                    lines.append(f'- **{hint["question"]}**')
                    lines.append(f'  {hint["preview"]}')
                else:
                    lines.append(f'- {hint}')
            lines.append('')

        return '\n'.join(lines)
