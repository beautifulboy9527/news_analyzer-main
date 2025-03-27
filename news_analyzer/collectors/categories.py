"""
新闻分类管理模块

定义标准新闻分类体系，并提供分类管理功能
"""

# 标准分类体系
STANDARD_CATEGORIES = {
    "general": {
        "name": "综合新闻",
        "description": "国内外综合新闻报道",
        "sources": []
    },
    "international": {
        "name": "国际新闻",
        "description": "国际时事和外交新闻",
        "sources": []
    },
    "technology": {
        "name": "科技新闻", 
        "description": "科技行业和创新动态",
        "sources": []
    },
    "business": {
        "name": "商业金融",
        "description": "商业、经济和金融市场",
        "sources": []
    },
    "politics": {
        "name": "政治新闻",
        "description": "国内外政治动态",
        "sources": []
    },
    "science": {
        "name": "科学新闻",
        "description": "科学研究和发展",
        "sources": []
    },
    "sports": {
        "name": "体育新闻",
        "description": "体育赛事和运动员动态",
        "sources": []
    },
    "entertainment": {
        "name": "娱乐新闻",
        "description": "影视、音乐和名人动态",
        "sources": []
    },
    "health": {
        "name": "健康医疗",
        "description": "医疗健康和养生",
        "sources": []
    },
    "culture": {
        "name": "文化教育",
        "description": "文化、艺术和教育",
        "sources": []
    }
}

def get_standard_categories():
    """获取标准分类体系"""
    return STANDARD_CATEGORIES

def get_category_name(category_id):
    """根据分类ID获取分类名称"""
    return STANDARD_CATEGORIES.get(category_id, {}).get("name", "未分类")

def validate_category(category_id):
    """验证分类ID是否有效"""
    return category_id in STANDARD_CATEGORIES