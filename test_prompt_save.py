# 测试提示词保存功能
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from stock_ai_comprehensive_analyzer import StockAIComprehensiveAnalyzer

def test_save_prompt():
    # 使用测试数据文件
    file_path = './data/002384.SZ/002384.SZ_indicators.csv'
    
    # 创建分析器实例
    analyzer = StockAIComprehensiveAnalyzer(file_path)
    
    # 加载数据
    analyzer.load_data()
    
    # 加载分析报告
    analyzer.load_analysis_reports()
    
    # 生成提示词
    prompt = analyzer.generate_ai_prompt()
    print(f"生成的提示词长度: {len(prompt)} 字符")
    
    # 保存提示词到txt文件
    file_path = analyzer.save_prompt_to_txt(prompt)
    print(f"提示词已保存到: {file_path}")
    
    # 检查文件是否存在
    if os.path.exists(file_path):
        print("文件创建成功！")
        # 读取文件内容的前1000个字符
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read(1000)
            print("\n文件内容预览:")
            print(content)
            print("...")
    else:
        print("文件创建失败！")

if __name__ == "__main__":
    test_save_prompt()
