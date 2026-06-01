# analyze_performance_forecast.py
# -*- coding: utf-8 -*-
"""
业绩预告与分红数据分析工具
分析300433.SZ的业绩预告和分红数据
"""

import os
import json
import argparse
from datetime import datetime
import pandas as pd

# 从config模块导入配置
from config import DATA_DIR, AI_CONFIG

class PerformanceForecastAnalyzer:
    """业绩预告与分红数据分析师"""
    
    def __init__(self, ticker: str):
        """
        初始化分析师
        :param ticker: 股票代码，例如：300433.SZ
        """
        self.ticker = ticker
        self.stock_dir = os.path.join(DATA_DIR, ticker)
        self.data = {
            'performance': None,      # 机构研报预测
            'performance_ths': None,  # 同花顺业绩预测
            'ex_dividend': None       # 除权除息数据
        }
        self.company_name = None
    
    def load_data(self) -> bool:
        """加载三类数据"""
        print(f"\n[{self.ticker}] 加载业绩预告与分红数据...")
        
        # 加载机构研报预测数据
        performance_file = os.path.join(self.stock_dir, f"{self.ticker}_performance_forecast.csv")
        if os.path.exists(performance_file):
            try:
                self.data['performance'] = pd.read_csv(performance_file)
                print(f"  加载机构研报预测数据: {len(self.data['performance'])} 条记录")
                # 读取公司名称
                if not self.company_name and not self.data['performance'].empty:
                    self.company_name = self.data['performance'].iloc[0]['名称']
                    print(f"  识别到公司名称: {self.company_name}")
            except Exception as e:
                print(f"  加载机构研报预测数据时出错: {e}")
        else:
            print(f"  机构研报预测数据文件不存在: {performance_file}")
        
        # 加载同花顺业绩预测数据
        performance_ths_file = os.path.join(self.stock_dir, f"{self.ticker}_performance_forecast_ths.csv")
        if os.path.exists(performance_ths_file):
            try:
                self.data['performance_ths'] = pd.read_csv(performance_ths_file)
                print(f"  加载同花顺业绩预测数据: {len(self.data['performance_ths'])} 条记录")
            except Exception as e:
                print(f"  加载同花顺业绩预测数据时出错: {e}")
        else:
            print(f"  同花顺业绩预测数据文件不存在: {performance_ths_file}")
        
        # 加载除权除息数据
        ex_dividend_file = os.path.join(self.stock_dir, f"{self.ticker}_ex_dividend.csv")
        if os.path.exists(ex_dividend_file):
            try:
                self.data['ex_dividend'] = pd.read_csv(ex_dividend_file)
                print(f"  加载除权除息数据: {len(self.data['ex_dividend'])} 条记录")
                # 如果还没有公司名称，从这里读取
                if not self.company_name and not self.data['ex_dividend'].empty:
                    self.company_name = self.data['ex_dividend'].iloc[0]['名称']
                    print(f"  识别到公司名称: {self.company_name}")
            except Exception as e:
                print(f"  加载除权除息数据时出错: {e}")
        else:
            print(f"  除权除息数据文件不存在: {ex_dividend_file}")
        
        # 检查是否有数据加载成功
        return any(df is not None for df in self.data.values())
    
    def analyze_institutional_ratings(self) -> str:
        """分析机构评级"""
        if self.data['performance'] is None or self.data['performance'].empty:
            return "暂无机构评级数据"
        
        data = self.data['performance'].iloc[0]
        total_reports = data['研报数']
        buy = data['机构投资评级(近六个月)-买入']
        increase = data['机构投资评级(近六个月)-增持']
        neutral = data['机构投资评级(近六个月)-中性']
        reduce = data['机构投资评级(近六个月)-减持']
        sell = data['机构投资评级(近六个月)-卖出']
        
        # 计算评级比例
        buy_ratio = (buy / total_reports * 100) if total_reports > 0 else 0
        increase_ratio = (increase / total_reports * 100) if total_reports > 0 else 0
        neutral_ratio = (neutral / total_reports * 100) if total_reports > 0 else 0
        reduce_ratio = (reduce / total_reports * 100) if total_reports > 0 else 0
        sell_ratio = (sell / total_reports * 100) if total_reports > 0 else 0
        
        # 评级分析
        positive_ratings = buy + increase
        positive_ratio = (positive_ratings / total_reports * 100) if total_reports > 0 else 0
        
        analysis = "## 1. 机构评级分析\n"
        analysis += f"- 研报总数: {total_reports} 份\n"
        analysis += f"- 买入评级: {buy} 家 ({buy_ratio:.1f}%)\n"
        analysis += f"- 增持评级: {increase} 家 ({increase_ratio:.1f}%)\n"
        analysis += f"- 中性评级: {neutral} 家 ({neutral_ratio:.1f}%)\n"
        analysis += f"- 减持评级: {reduce} 家 ({reduce_ratio:.1f}%)\n"
        analysis += f"- 卖出评级: {sell} 家 ({sell_ratio:.1f}%)\n"
        analysis += f"- 积极评级占比: {positive_ratings} 家 ({positive_ratio:.1f}%)\n"
        
        # 评级结论
        if positive_ratio >= 90:
            analysis += "- 评级结论: 机构强烈看好\n"
        elif positive_ratio >= 70:
            analysis += "- 评级结论: 机构普遍看好\n"
        elif positive_ratio >= 50:
            analysis += "- 评级结论: 机构略看好\n"
        else:
            analysis += "- 评级结论: 机构态度谨慎\n"
        
        return analysis
    
    def analyze_earnings_forecast(self) -> str:
        """分析业绩预测"""
        analysis = "## 2. 业绩预测分析\n"
        
        # 分析机构研报预测
        if self.data['performance'] is not None and not self.data['performance'].empty:
            data = self.data['performance'].iloc[0]
            analysis += "### 2.1 机构研报预测\n"
            analysis += f"- 2024年预测每股收益: {data['2024预测每股收益']:.4f} 元\n"
            analysis += f"- 2025年预测每股收益: {data['2025预测每股收益']:.4f} 元\n"
            analysis += f"- 2026年预测每股收益: {data['2026预测每股收益']:.4f} 元\n"
            analysis += f"- 2027年预测每股收益: {data['2027预测每股收益']:.4f} 元\n"
            
            # 计算增长率
            if '2024预测每股收益' in data and '2025预测每股收益' in data:
                if data['2024预测每股收益'] > 0:
                    growth_2025 = (data['2025预测每股收益'] - data['2024预测每股收益']) / data['2024预测每股收益'] * 100
                    analysis += f"- 2025年预测增长率: {growth_2025:.1f}%\n"
            if '2025预测每股收益' in data and '2026预测每股收益' in data:
                if data['2025预测每股收益'] > 0:
                    growth_2026 = (data['2026预测每股收益'] - data['2025预测每股收益']) / data['2025预测每股收益'] * 100
                    analysis += f"- 2026年预测增长率: {growth_2026:.1f}%\n"
            if '2026预测每股收益' in data and '2027预测每股收益' in data:
                if data['2026预测每股收益'] > 0:
                    growth_2027 = (data['2027预测每股收益'] - data['2026预测每股收益']) / data['2026预测每股收益'] * 100
                    analysis += f"- 2027年预测增长率: {growth_2027:.1f}%\n"
        else:
            analysis += "### 2.1 机构研报预测\n- 暂无数据\n"
        
        # 分析同花顺业绩预测
        if self.data['performance_ths'] is not None and not self.data['performance_ths'].empty:
            analysis += "\n### 2.2 同花顺业绩预测\n"
            for _, row in self.data['performance_ths'].iterrows():
                year = row['年度']
                institutions = row['预测机构数']
                min_eps = row['最小值']
                avg_eps = row['均值']
                max_eps = row['最大值']
                industry_avg = row['行业平均数']
                
                # 计算预测区间
                range_percent = ((max_eps - min_eps) / avg_eps * 100) if avg_eps > 0 else 0
                industry_diff = ((avg_eps - industry_avg) / industry_avg * 100) if industry_avg > 0 else 0
                
                analysis += f"- {year}年: {institutions}家机构预测\n"
                analysis += f"  预测区间: {min_eps:.4f} - {max_eps:.4f} 元 (均值: {avg_eps:.4f} 元)\n"
                analysis += f"  预测分歧度: {range_percent:.1f}%\n"
                analysis += f"  与行业平均对比: {industry_diff:.1f}%\n"
        else:
            analysis += "\n### 2.2 同花顺业绩预测\n- 暂无数据\n"
        
        return analysis
    
    def analyze_dividend(self) -> str:
        """分析分红数据"""
        if self.data['ex_dividend'] is None or self.data['ex_dividend'].empty:
            return "## 3. 分红分析\n- 暂无分红数据\n"
        
        data = self.data['ex_dividend'].iloc[0]
        analysis = "## 3. 分红分析\n"
        analysis += f"- 上市日期: {data['上市日期']}\n"
        analysis += f"- 累计股息: {data['累计股息']} 元\n"
        analysis += f"- 年均股息: {data['年均股息']} 元\n"
        analysis += f"- 分红次数: {data['分红次数']} 次\n"
        analysis += f"- 融资总额: {data['融资总额']} 亿元\n"
        analysis += f"- 融资次数: {data['融资次数']} 次\n"
        
        # 计算分红融资比
        if data['融资总额'] > 0:
            dividend_financing_ratio = (data['累计股息'] / data['融资总额'] * 100)
            analysis += f"- 分红融资比: {dividend_financing_ratio:.1f}%\n"
        
        # 分红政策评估
        listing_years = (datetime.now().year - int(data['上市日期'].split('-')[0]))
        if data['分红次数'] >= listing_years * 0.8:
            analysis += "- 分红政策评估: 积极分红\n"
        elif data['分红次数'] >= listing_years * 0.5:
            analysis += "- 分红政策评估: 稳健分红\n"
        else:
            analysis += "- 分红政策评估: 分红较少\n"
        
        return analysis
    
    def get_ai_analysis(self, analysis_report: str) -> str:
        """获取AI分析结果"""
        try:
            import ollama
            
            company_name_display = self.company_name if self.company_name else "未知公司"
            prompt = f"""你是一位专业的量化投资分析师，擅长从业绩预测和分红角度分析股票的投资价值。请基于以下分析报告，从量化投资的角度进行深入分析：

重要信息：股票代码 {self.ticker} 对应的公司名称是 {company_name_display}，请在分析中使用正确的公司名称。

{analysis_report}

=== 分析要求 ===
请从量化投资的角度分析以下内容：
1. 基于机构评级和业绩预测，评估公司的投资价值
2. 分析业绩预测的可靠性和潜在风险
3. 基于分红数据，评估公司的财务健康度和股东回报
4. 结合业绩预测和分红情况，给出投资建议
5. 分析业绩预测与行业平均的对比
6. 提供风险评估和投资策略建议

请提供详细、专业的分析，基于数据和量化指标，避免泛泛而谈。"""

            print(f"正在请求本地Ollama AI ({AI_CONFIG['model']})...")
            client = ollama.Client(host=AI_CONFIG['base_url'])
            
            response = client.chat(
                model=AI_CONFIG['model'],
                messages=[
                    {"role": "system", "content": "你是一位专业的量化投资分析师，擅长从业绩预测和分红角度分析股票的投资价值。"},
                    {"role": "user", "content": prompt}
                ],
                options={
                    "temperature": AI_CONFIG['temperature'],
                    "num_predict": AI_CONFIG['max_tokens']
                }
            )
            
            return response['message']['content']
        except Exception as e:
            print(f"调用本地Ollama AI时出错: {e}")
            return "无法获取AI分析，请检查Ollama服务是否正常运行。"
    
    def generate_report(self) -> str:
        """生成分析报告"""
        # 构建分析报告
        company_name_display = self.company_name if self.company_name else "未知公司"
        report = f"# {self.ticker} {company_name_display} 业绩预告与分红分析报告\n\n"
        report += f"## 分析时间\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        # 添加各类分析
        # report += self.analyze_institutional_ratings() + "\n"
        # report += self.analyze_earnings_forecast() + "\n"
        # report += self.analyze_dividend() + "\n"
        
        # 添加AI深度分析
        # report += "## 4. AI深度分析\n"
        report += self.get_ai_analysis(report) + "\n"
        
        # 保存报告
        report_filename = f"{self.ticker}_performance_analysis_{datetime.now().strftime('%Y%m%d')}.md"
        report_path = os.path.join(self.stock_dir, report_filename)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n分析报告已保存到: {report_path}")
        return report

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='业绩预告与分红数据分析工具')
    parser.add_argument('--ticker', type=str, default='300433.SZ', help='股票代码，默认300433.SZ')
    
    args = parser.parse_args()
    ticker = args.ticker
    
    print(f"开始分析 {ticker} 的业绩预告与分红数据...")
    
    # 初始化分析器
    analyzer = PerformanceForecastAnalyzer(ticker)
    
    # 加载数据
    if not analyzer.load_data():
        print("错误：无法加载任何数据文件")
        return
    
    # 生成分析报告
    analyzer.generate_report()
    
    print("\n分析完成！")

if __name__ == "__main__":
    main()
