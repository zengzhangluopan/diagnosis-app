# 电商链接诊断 V2.0

## 快速启动

### 1. 安装依赖
```
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2. 启动应用
```
python -m streamlit run app.py --server.port 8501 --server.headless true
```

### 3. 打开浏览器
访问 http://localhost:8501

## 需要的数据文件
从生意参谋和阿里妈妈导出3个文件：
1. **商品概况** — 生意参谋 → 商品 → 商品概况 → 导出
2. **流量来源** — 生意参谋 → 流量 → 商品二级来源 → 导出
3. **推广报表** — 阿里妈妈 → 报表 → 计划报表 → 导出

## 功能
- 18维度评分（流量端/转化端/产品端）
- 推广深度分析（真实ROI、归因虚高、蓄水效率）
- 拉新/收割分层诊断
- 归因修正（剥离自然流量虚高）
- 数据完整性校验
- 术语说明

## 技术栈
- Python 3.10+
- Streamlit（Web界面）
- xlrd + openpyxl（Excel解析）
