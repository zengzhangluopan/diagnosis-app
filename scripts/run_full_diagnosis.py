#!/usr/bin/env python3
"""
一站式诊断脚本 V1.0 (2026-06-12)
将文件解析 + 诊断引擎合并为一次调用，避免Bot中间停顿

用法:
  python scripts/run_full_diagnosis.py '<文件路径1>' '<文件路径2>' '<文件路径3>'

可选参数（通过环境变量）:
  PRODUCT_PREFIX=CG104  — 指定推广报表中的商品前缀

输出: 完整诊断结论JSON（one_liner + actions + data_card）
"""

import sys
import json
import os

# 添加项目根目录到path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)
# 也添加scripts目录，方便直接import
sys.path.insert(0, os.path.join(_project_root, 'scripts'))

from parse_csv import parse_files
from run_diagnosis import run_diagnosis


def main():
    if len(sys.argv) < 2:
        result = {
            'error': '请提供文件路径',
            'usage': "python run_full_diagnosis.py '文件1' '文件2' '文件3'"
        }
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

    file_paths = sys.argv[1:]

    # Step 1: 解析文件
    try:
        parsed = parse_files(file_paths)
    except Exception as e:
        print(json.dumps({'error': f'文件解析失败: {str(e)}'}, ensure_ascii=False))
        sys.exit(1)

    # 检查解析错误
    if '_errors' in parsed:
        errors = parsed.pop('_errors')
        if not parsed:  # 没有有效数据
            print(json.dumps({'error': f'文件解析失败: {"; ".join(errors)}'}, ensure_ascii=False))
            sys.exit(1)

    # Step 2: 处理多商品情况
    available_prefixes = parsed.pop('_available_prefixes', None)

    # 如果环境变量指定了product_prefix，优先使用（跳过选择步骤）
    env_prefix = os.environ.get('PRODUCT_PREFIX', '')
    if env_prefix:
        parsed['product_prefix'] = env_prefix
    elif available_prefixes and len(available_prefixes) > 1:
        # 多个商品且未指定 → 返回商品列表，让Bot问用户选哪个
        # 这是唯一需要停下来的情况
        result = {
            'status': 'need_selection',
            'message': '推广报表包含多个商品，请选择要诊断的商品',
            'available_products': list(available_prefixes.keys()),
            'parsed_data': parsed  # 保留已解析的数据，下次不用重新解析
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # Step 3: 运行诊断
    try:
        conclusion = run_diagnosis(parsed)
        print(json.dumps(conclusion, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({'error': f'诊断引擎运行失败: {str(e)}'}, ensure_ascii=False))
        sys.exit(1)


if __name__ == '__main__':
    main()
