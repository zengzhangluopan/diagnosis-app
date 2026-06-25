"""
18维度诊断 - CSV数据解析器
版本: V1.0
更新: 2026-05-25

支持解析以下生意参谋导出的CSV:
1. 搜索词报告 (search_terms.csv)
2. 流量来源报告 (traffic_source.csv)
3. 商品概况 (product_overview.csv)
4. 人群画像 (audience_profile.csv)
5. 转化漏斗 (conversion_funnel.csv)
6. 评价概览 (review_summary.csv)
7. 客服数据 (customer_service.csv)
8. DSR数据 (dsr.csv)

使用方式:
  from csv_parser import DataParser
  parser = DataParser("./data")
  parsed = parser.parse_all()
  # parsed 就是 DiagnosisEngine 需要的 raw_data
"""

import csv
import os
import json
from datetime import datetime


class DataParser:
    """解析生意参谋导出的CSV数据"""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.parsed = {}
    
    def parse_all(self) -> dict:
        """解析所有CSV文件，返回评分引擎需要的raw_data"""
        
        # 1. 搜索词报告 → 流量质量精准度
        self._parse_search_terms()
        
        # 2. 流量来源报告 → 各渠道流量占比
        self._parse_traffic_source()
        
        # 3. 商品概况 → 市场接受度、销量基数、SKU覆盖
        self._parse_product_overview()
        
        # 4. 转化漏斗 → 流量-页面匹配度、客服询单转化
        self._parse_conversion_funnel()
        
        # 5. 评价概览 → 评价质量
        self._parse_review_summary()
        
        # 6. DSR数据
        self._parse_dsr()
        
        # 7. 客服数据
        self._parse_customer_service()
        
        # 8. 人群画像 → 流量质量精准度(补充)
        self._parse_audience_profile()
        
        # 9. 自动填充时间节点
        self._auto_fill_time_node()
        
        return self.parsed
    
    def _read_csv(self, filename: str) -> list:
        """读取CSV文件，返回字典列表"""
        filepath = os.path.join(self.data_dir, filename)
        if not os.path.exists(filepath):
            return []
        
        rows = []
        encodings = ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']
        
        for enc in encodings:
            try:
                with open(filepath, 'r', encoding=enc) as f:
                    # 生意参谋CSV可能有BOM
                    content = f.read()
                    if content.startswith('\ufeff'):
                        content = content[1:]
                    
                    reader = csv.DictReader(content.splitlines())
                    for row in reader:
                        # 清理key的前后空格
                        cleaned = {k.strip(): v.strip() if isinstance(v, str) else v for k, v in row.items()}
                        rows.append(cleaned)
                break
            except (UnicodeDecodeError, FileNotFoundError):
                continue
        
        return rows
    
    def _safe_float(self, value, default=0.0):
        """安全转浮点数，处理百分比等格式"""
        if value is None or value == '' or value == '-':
            return default
        if isinstance(value, (int, float)):
            return float(value)
        # 去掉百分号
        s = str(value).replace('%', '').replace('％', '').replace(',', '').strip()
        try:
            v = float(s)
            # 如果原始值带%且小于1，转换为小数比例；否则保持原值
            # 百分比通常存为 65.3 这种形式，不带%时是0.653
            if '%' in str(value) and v <= 1:
                return v * 100
            return v
        except ValueError:
            return default
    
    def _parse_search_terms(self):
        """解析搜索词报告 → 精准词占比、质量分"""
        rows = self._read_csv('search_terms.csv')
        if not rows:
            return
        
        # 预期列: 搜索词, 搜索人气, 搜索热度, 点击率, 点击人气, 支付转化率, 直通车质量分(如有)
        total_search_volume = 0
        precise_search_volume = 0
        quality_scores = []
        
        # 简单的精准词判断逻辑：
        # 1. 词长>=4字（长尾词更精准）
        # 2. 包含品类核心词（如"净水器""滤芯"）
        # 3. 转化率>行业均值
        # 注：精准词列表需要根据具体品类配置
        
        for row in rows:
            keyword = row.get('搜索词', row.get('关键词', ''))
            volume = self._safe_float(row.get('搜索人气', row.get('搜索热度', 0)))
            conv_rate = self._safe_float(row.get('支付转化率', 0))
            quality = self._safe_float(row.get('质量分', row.get('直通车质量分', 0)))
            
            total_search_volume += volume
            
            if quality > 0:
                quality_scores.append(quality)
            
            # 精准词判断：词长>=4 或 转化率较高
            is_precise = len(keyword) >= 4 or conv_rate >= 3
            if is_precise:
                precise_search_volume += volume
        
        if total_search_volume > 0:
            precise_ratio = round(precise_search_volume / total_search_volume * 100, 1)
        else:
            precise_ratio = 0
        
        avg_quality = round(sum(quality_scores) / len(quality_scores), 1) if quality_scores else 5.0
        
        if 'traffic_quality' not in self.parsed:
            self.parsed['traffic_quality'] = {}
        self.parsed['traffic_quality']['precise_keyword_ratio'] = precise_ratio
        self.parsed['traffic_quality']['paid_keyword_quality_score'] = avg_quality
    
    def _parse_traffic_source(self):
        """解析流量来源报告 → 各渠道流量占比"""
        rows = self._read_csv('traffic_source.csv')
        if not rows:
            return
        
        # 预期列: 流量来源, 访客数, 下单买家数, 下单金额, 支付转化率
        total_visitors = 0
        channel_visitors = {
            'search': 0,
            'recommend': 0,
            'content': 0,
            'cart_fav': 0,
            'other': 0,
        }
        
        for row in rows:
            source = row.get('流量来源', row.get('来源', ''))
            visitors = self._safe_float(row.get('访客数', 0))
            total_visitors += visitors
            
            source_lower = source.lower()
            if any(kw in source for kw in ['搜索', '自然搜索', '直通车', '付费搜索']):
                channel_visitors['search'] += visitors
            elif any(kw in source for kw in ['推荐', '猜你喜欢', '购物意图']):
                channel_visitors['recommend'] += visitors
            elif any(kw in source for kw in ['内容', '直播', '短视频', '达人', '逛逛']):
                channel_visitors['content'] += visitors
            elif any(kw in source for kw in ['加购', '收藏', '已买', '我的']):
                channel_visitors['cart_fav'] += visitors
            else:
                channel_visitors['other'] += visitors
        
        if total_visitors > 0:
            if 'traffic_quality' not in self.parsed:
                self.parsed['traffic_quality'] = {}
            self.parsed['traffic_quality']['search_traffic_ratio'] = round(channel_visitors['search'] / total_visitors, 2)
            self.parsed['traffic_quality']['recommend_traffic_ratio'] = round(channel_visitors['recommend'] / total_visitors, 2)
            self.parsed['traffic_quality']['content_traffic_ratio'] = round(channel_visitors['content'] / total_visitors, 2)
            self.parsed['traffic_quality']['cart_fav_traffic_ratio'] = round(channel_visitors['cart_fav'] / total_visitors, 2)
    
    def _parse_product_overview(self):
        """解析商品概况 → 市场接受度、销量基数、SKU覆盖"""
        rows = self._read_csv('product_overview.csv')
        if not rows:
            return
        
        # 商品概况可能是单行数据
        row = rows[0]
        
        # 市场接受度
        sell_through = self._safe_float(row.get('动销率', 0))
        cart_add_rate = self._safe_float(row.get('加购率', 0))
        conv_vs_industry = self._safe_float(row.get('转化率行业对比', 1.0))
        if conv_vs_industry > 2:  # 可能是百分比而非比值
            conv_vs_industry = conv_vs_industry / 100
        
        self.parsed['market_acceptance'] = {
            'sell_through_rate': sell_through,
            'cart_add_rate': cart_add_rate,
            'natural_conv_vs_industry': conv_vs_industry,
        }
        
        # 销量基数
        monthly_sales = int(self._safe_float(row.get('支付件数', row.get('月销量', 0))))
        self.parsed['sales_base'] = {
            'monthly_sales': monthly_sales,
            'same_price_rank': int(self._safe_float(row.get('同价位排名', 5))),
            'sales_trend': int(self._safe_float(row.get('销量趋势', 3))),
        }
        
        # SKU覆盖
        total_skus = int(self._safe_float(row.get('SKU总数', 0)))
        zero_sales = int(self._safe_float(row.get('零销量SKU数', 0)))
        top5_conc = self._safe_float(row.get('TOP5销量集中度', 0))
        
        self.parsed['sku_coverage'] = {
            'zero_sales_sku_ratio': round(zero_sales / total_skus * 100, 1) if total_skus > 0 else 50,
            'top5_sales_concentration': top5_conc if top5_conc <= 100 else top5_conc,
            'price_band_coverage': int(self._safe_float(row.get('价格带覆盖', 3))),
        }
    
    def _parse_conversion_funnel(self):
        """解析转化漏斗 → 流量-页面匹配度"""
        rows = self._read_csv('conversion_funnel.csv')
        if not rows:
            return
        
        row = rows[0]
        
        bounce_rate = self._safe_float(row.get('跳失率', 0))
        keyword_coverage = self._safe_float(row.get('搜索词覆盖度', 0))
        has_landing = row.get('渠道落地页', '无') in ['有', 'True', 'true', '1', 'yes']
        
        self.parsed['traffic_page_match'] = {
            'precise_bounce_rate': bounce_rate,
            'top20_keyword_coverage': keyword_coverage,
            'has_channel_landing_pages': has_landing,
        }
        
        # 主图点击率
        ctr = self._safe_float(row.get('主图点击率', 0))
        industry_ctr = self._safe_float(row.get('行业点击率', 3.5))
        if ctr > 0:
            self.parsed['main_image_ctr'] = {
                'main_image_ctr': ctr,
                'industry_avg_ctr': industry_ctr,
            }
        
        # 位置排名
        rank_page = self._safe_float(row.get('核心词排名页数', 0))
        natural_ratio = self._safe_float(row.get('自然流量占比', 0))
        if rank_page > 0:
            self.parsed['position_rank'] = {
                'core_keyword_rank_page': rank_page,
                'natural_traffic_ratio': natural_ratio,
            }
        
        # 价格定位
        price_rank = self._safe_float(row.get('价格排名百分位', 0))
        promo_ratio = self._safe_float(row.get('促销转化倍数', 0))
        price_complaint = self._safe_float(row.get('价格差评占比', 0))
        if price_rank > 0 or promo_ratio > 0:
            self.parsed['price_positioning'] = {
                'price_rank_percentile': price_rank,
                'promo_vs_daily_conv_ratio': promo_ratio if promo_ratio > 0 else 2.0,
                'price_complaint_ratio': price_complaint,
            }
        
        # 营销方案
        promo_freq = self._safe_float(row.get('促销频率', 0))
        promo_roi = self._safe_float(row.get('促销ROI', 0))
        daily_promo_ratio = self._safe_float(row.get('日常促销转化比', 0))
        if promo_freq > 0:
            self.parsed['marketing'] = {
                'promo_frequency': promo_freq,
                'promo_roi': promo_roi if promo_roi > 0 else 2.0,
                'daily_vs_promo_conv_ratio': daily_promo_ratio if daily_promo_ratio > 0 else 0.4,
            }
        
        # 服务承诺 & 发货
        warranty = self._safe_float(row.get('质保月数', 12))
        has_7day = row.get('7天无理由', '有') in ['有', 'True', 'true', '1', 'yes']
        dispute = self._safe_float(row.get('纠纷率', 0))
        
        self.parsed['service_promise'] = {
            'warranty_months': int(warranty),
            'has_7day_return': has_7day,
            'dispute_rate': dispute,
        }
        
        shipping_rate = self._safe_float(row.get('发货达标率', 0))
        free_ship = row.get('全场包邮', '否') in ['是', 'True', 'true', '1', 'yes']
        logistics_complaint = self._safe_float(row.get('物流差评占比', 0))
        
        self.parsed['shipping'] = {
            'shipping_on_time_rate': shipping_rate if shipping_rate > 0 else 90,
            'free_shipping': free_ship,
            'logistics_complaint_ratio': logistics_complaint,
        }
    
    def _parse_review_summary(self):
        """解析评价概览 → 评价质量"""
        rows = self._read_csv('review_summary.csv')
        if not rows:
            return
        
        row = rows[0]
        
        self.parsed['review_quality'] = {
            'good_review_rate': self._safe_float(row.get('好评率', 0)),
            'image_review_ratio': self._safe_float(row.get('有图评价占比', 0)),
            'core_complaint_ratio': self._safe_float(row.get('核心差评占比', 0)),
        }
        
        # 问大家
        pos_ratio = self._safe_float(row.get('问大家正面占比', 0))
        seller_cover = self._safe_float(row.get('卖家回答覆盖率', 0))
        if pos_ratio > 0:
            self.parsed['wen_dajia'] = {
                'positive_answer_ratio': pos_ratio,
                'seller_answer_coverage': seller_cover,
            }
    
    def _parse_dsr(self):
        """解析DSR数据"""
        rows = self._read_csv('dsr.csv')
        if not rows:
            return
        
        row = rows[0]
        self.parsed['dsr'] = {
            'desc_score': self._safe_float(row.get('描述相符', row.get('描述', 4.7))),
            'service_score': self._safe_float(row.get('服务态度', row.get('服务', 4.7))),
            'logistics_score': self._safe_float(row.get('物流速度', row.get('物流', 4.7))),
            'industry_avg': self._safe_float(row.get('行业均值', 4.75)),
        }
    
    def _parse_customer_service(self):
        """解析客服数据"""
        rows = self._read_csv('customer_service.csv')
        if not rows:
            return
        
        row = rows[0]
        self.parsed['customer_service'] = {
            'inquiry_conv_rate': self._safe_float(row.get('询单转化率', 0)),
            'avg_response_time_sec': self._safe_float(row.get('平均响应时间(秒)', row.get('响应时间', 60))),
        }
    
    def _parse_audience_profile(self):
        """解析人群画像 → 流量质量精准度(补充)"""
        rows = self._read_csv('audience_profile.csv')
        if not rows:
            return
        
        row = rows[0]
        
        if 'traffic_quality' not in self.parsed:
            self.parsed['traffic_quality'] = {}
        
        self.parsed['traffic_quality']['audience_overlap'] = self._safe_float(
            row.get('人群重合度', row.get('目标客群重合度', 50))
        )
        
        # 推荐渠道数据
        rec_overlap = self._safe_float(row.get('推荐人群重合度', 0))
        rec_fav_cart = self._safe_float(row.get('推荐收藏加购率', 0))
        if rec_overlap > 0:
            self.parsed['traffic_quality']['recommend_audience_overlap'] = rec_overlap
        if rec_fav_cart > 0:
            self.parsed['traffic_quality']['recommend_fav_cart_rate'] = rec_fav_cart
        
        # 内容渠道数据
        content_overlap = self._safe_float(row.get('内容人群重合度', 0))
        content_bounce = self._safe_float(row.get('内容跳失率', 0))
        if content_overlap > 0:
            self.parsed['traffic_quality']['content_audience_overlap'] = content_overlap
        if content_bounce > 0:
            self.parsed['traffic_quality']['content_bounce_rate'] = content_bounce
        
        # 加购收藏渠道
        cart_conv = self._safe_float(row.get('加购转化率', 0))
        fav_conv = self._safe_float(row.get('收藏转化率', 0))
        if cart_conv > 0:
            self.parsed['traffic_quality']['cart_conv_rate'] = cart_conv
        if fav_conv > 0:
            self.parsed['traffic_quality']['fav_conv_rate'] = fav_conv
    
    def _auto_fill_time_node(self):
        """自动填充时间节点"""
        self.parsed['time_node'] = {
            'current_date_str': datetime.now().strftime('%Y-%m-%d'),
            'industry_search_trend': 3,  # 默认稳定，需人工调整
        }


# ============================================================
# 命令行入口
# ============================================================

if __name__ == '__main__':
    import sys
    
    data_dir = sys.argv[1] if len(sys.argv) > 1 else './data'
    
    print(f'正在解析数据目录: {data_dir}')
    
    parser = DataParser(data_dir)
    parsed = parser.parse_all()
    
    print(f'解析完成，共获取 {len(parsed)} 个维度的数据:')
    for k, v in parsed.items():
        print(f'  {k}: {json.dumps(v, ensure_ascii=False, default=str)}')
    
    # 如果解析到了数据，直接跑诊断
    if parsed:
        from scoring_engine import DiagnosisEngine
        engine = DiagnosisEngine(parsed)
        result = engine.run()
        
        print(f'\n综合得分: {result["total_score"]} / 10 ({result["total_status"]})')
        print(f'最薄弱环节: {result["weakest_layer"]}')
        
        # 保存报告
        output_path = os.path.join(data_dir, '..', 'output', '诊断报告.md')
        DiagnosisEngine.save_report(result, output_path)
        print(f'报告已保存: {output_path}')
