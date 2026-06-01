# financial_analysis_enhancer.py
"""
财务分析增强器
功能：读取财务结构化摘要，调用本地LLM进行深度分析，将分析结果添加到摘要中。
特点：
1. 读取已生成的 {ticker}_financial_summary.json
2. 构建专业的财务分析提示词
3. 调用Ollama进行深度分析
4. 将分析结果保存回JSON文件
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATA_DIR, AI_CONFIG


class FinancialAnalysisEnhancer:
    """财务分析增强器"""

    def __init__(self, ticker: str):
        self.ticker = ticker
        self.stock_dir = os.path.join(DATA_DIR, ticker)
        self.summary_path = os.path.join(self.stock_dir, f"{ticker}_financial_summary.json")
        self.summary = {}
        self.company_name = None

    def load_summary(self) -> bool:
        """加载已生成的财务结构化摘要"""
        if not os.path.exists(self.summary_path):
            print(f"错误：文件不存在 {self.summary_path}")
            return False
        
        try:
            with open(self.summary_path, 'r', encoding='utf-8') as f:
                self.summary = json.load(f)
            
            # 获取公司名称
            self.company_name = self.summary.get('meta', {}).get('company_name', '未知公司')
            print(f"已加载 {self.company_name}({self.ticker}) 的财务摘要")
            return True
        except Exception as e:
            print(f"加载文件失败: {e}")
            return False

    def build_analysis_prompt(self) -> str:
        """构建简洁的财务分析提示词"""
        # 提取关键数据
        verdict = self.summary.get('verdict', {})
        key_metrics = self.summary.get('key_metrics', {})
        detailed_metrics = self.summary.get('detailed_metrics', {})
        anomalies = self.summary.get('major_anomalies', [])
        risk_tags = self.summary.get('risk_tags', [])
        industry_comparison = self.summary.get('industry_comparison', {})

        # 构建精简的数据摘要
        data_summary = []
        
        # 基本信息
        data_summary.append(f"公司: {self.company_name} ({self.ticker})")
        data_summary.append(f"信号: {verdict.get('signal', 'N/A')}")
        data_summary.append(f"建议: {self.summary.get('suggested_action', 'N/A')}")
        
        # 关键指标（精简版
        key_str = ", ".join([f"{k}:{v}" for k, v in list(key_metrics.items())[:6]])
        data_summary.append(f"关键指标: {key_str}")
        
        # 主要异常
        if anomalies:
            anomaly_str = ", ".join([f"{a.get('type', '')}" for a in anomalies[:3]])
            data_summary.append(f"主要风险: {anomaly_str}")
        
        # 构建数据摘要文本（避免在f-string中使用\n）
        data_text = "\n".join(data_summary)
        
        prompt = f"""你是量化投资分析师，基于以下{self.company_name}({self.ticker})的财务数据，给出简洁明确的分析。

数据概览:
{data_text}

按以下格式输出，每项不超过3点:

1. 核心结论:
2. 主要风险:
3. 投资建议:

请简洁明了，无需详细分析，直接给出结论。
"""
        return prompt

    def get_ai_analysis(self, prompt: str) -> str:
        """调用Ollama获取简洁版AI分析结果"""
        try:
            import ollama
            
            print(f"正在请求本地Ollama AI ({AI_CONFIG['model']})...")
            
            client = ollama.Client(host=AI_CONFIG['base_url'])
            
            response = client.chat(
                model=AI_CONFIG['model'],
                messages=[
                    {"role": "system", "content": "你是专业的量化投资分析师，请用简洁明了的中文输出分析结论。"},
                    {"role": "user", "content": prompt}
                ],
                options={
                    "temperature": 0.1,
                    "num_predict": 800
                }
            )
            
            analysis = response['message']['content'].strip()
            print("AI分析完成")
            return analysis
            
        except ImportError:
            print("错误：未安装ollama库，请先安装")
            return ""
        except Exception as e:
            print(f"AI分析失败: {e}")
            return ""

    def save_enhanced_summary(self, analysis: str):
        """将简洁版分析结果保存：完整分析另存为MD文件，JSON中保留完整简洁分析"""
        
        # 1. 将AI分析报告另存为独立的MD文件
        report_path = os.path.join(self.stock_dir, f"{self.ticker}_ai_analysis.md")
        report_content = f"""# {self.company_name} ({self.ticker}) 财务分析

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**使用模型**: {AI_CONFIG['model']}

---

{analysis}
"""
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        print(f"AI分析报告已保存至 {report_path}")
        
        # 2. 在JSON中保留完整的简洁分析
        self.summary['ai_summary'] = {
            'analysis': analysis,
            'report_path': report_path,
            'generated_at': datetime.now().isoformat(),
            'model': AI_CONFIG['model']
        }
        
        # 更新生成时间
        if 'meta' in self.summary:
            self.summary['meta']['ai_analyzed_at'] = datetime.now().isoformat()
        
        # 如果存在旧的ai_analysis字段，删除它
        if 'ai_analysis' in self.summary:
            del self.summary['ai_analysis']
        
        with open(self.summary_path, 'w', encoding='utf-8') as f:
            json.dump(self.summary, f, ensure_ascii=False, indent=2)
        
        print(f"财务摘要已更新，仅包含AI摘要（不含长文本）")

    def run(self):
        """主流程"""
        print(f"\n{'='*60}")
        print(f"开始增强 {self.ticker} 财务分析")
        print(f"{'='*60}")
        
        # 1. 加载财务摘要
        if not self.load_summary():
            return
        
        # 2. 构建提示词
        prompt = self.build_analysis_prompt()
        
        # 3. 获取AI分析
        analysis = self.get_ai_analysis(prompt)
        if not analysis:
            print("AI分析失败，跳过保存")
            return
        
        # 4. 保存增强后的摘要
        self.save_enhanced_summary(analysis)
        
        print(f"\n{'='*60}")
        print("完成财务分析增强")
        print(f"{'='*60}")
        print("\nAI分析摘要：")
        print("-" * 40)
        # 只显示前500字符
        print(analysis[:500] + "..." if len(analysis) > 500 else analysis)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="增强财务分析，调用AI进行深度分析")
    parser.add_argument('--ticker', required=True, help="股票代码，如 300433.SZ")
    args = parser.parse_args()

    enhancer = FinancialAnalysisEnhancer(args.ticker)
    enhancer.run()


if __name__ == "__main__":
    main()