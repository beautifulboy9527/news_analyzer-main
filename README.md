# 新闻聚合与分析系统

## 项目概述
这是一个基于Python的新闻聚合与分析系统，主要功能包括：
- 从多个新闻源(RSS/澎湃新闻)采集新闻
- 新闻内容分析与分类
- 基于LLM的智能摘要和情感分析
- 历史记录管理和数据导出

## 主要功能
1. **新闻采集**:
   - RSS新闻源采集
   - 澎湃新闻爬取
   - 自动分类和标签

2. **新闻分析**:
   - 关键词提取
   - 情感分析
   - 自动摘要生成
   - 主题聚类

3. **用户界面**:
   - 新闻列表展示
   - 分类浏览
   - 搜索功能
   - 分析结果可视化

## 技术栈
- Python 3.10+
- PyQt5 (GUI界面)
- Requests/Feedparser (数据采集)
- BeautifulSoup4 (HTML解析)
- Jieba (中文分词)
- Transformers (LLM集成)

## 安装指南
1. 克隆仓库:
```bash
git clone https://github.com/your-repo/news_analyzer.git
```

2. 安装依赖:
```bash
pip install -r requirements.txt
```

3. 运行程序:
```bash
python main.py
```

## 文件结构
```
news_analyzer/
├── collectors/      # 新闻采集模块
├── config/          # 配置管理  
├── core/            # 核心业务逻辑
├── data/            # 数据存储
├── llm/             # 大语言模型集成
├── models/          # 数据模型
├── storage/         # 存储管理
├── ui/              # 用户界面
└── logs/            # 日志文件
```

## 注意事项
1. 使用前需配置LLM API密钥
2. 首次运行会自动创建数据目录
3. 建议定期清理logs目录
