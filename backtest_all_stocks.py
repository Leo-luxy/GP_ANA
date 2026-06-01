# backtest_all_stocks.py
# 批量回测所有股票
# --mode full:  严格多头排列 (MA5>MA10>MA20>MA60)
# --mode simple: 宽松多头排列 (MA5>MA20)
import os
import pandas as pd
import numpy as np
from datetime import datetime
from trend_following_backtest import TrendFollowingStrategy

try:
    from config import DATA_DIR
except ImportError:
    DATA_DIR = "./data"

def get_all_stocks():
    """获取data目录下所有股票代码"""
    stocks = []
    if os.path.exists(DATA_DIR):
        for item in os.listdir(DATA_DIR):
            item_path = os.path.join(DATA_DIR, item)
            if os.path.isdir(item_path):
                indicators_file = os.path.join(item_path, f"{item}_indicators.csv")
                if os.path.exists(indicators_file):
                    stocks.append(item)
    return sorted(stocks)

def run_batch_backtest(mode='full'):
    """批量回测所有股票"""
    stocks = get_all_stocks()
    mode_label = '严格多头排列' if mode == 'full' else '宽松多头排列'
    print(f"找到 {len(stocks)} 只股票")
    print(f"\n📌 策略模式: {mode_label} ({mode})")

    results = []
    timestamp = datetime.now().strftime('%Y%m%d')

    for ticker in stocks:
        print(f"\n=== 分析 {ticker} ===")

        try:
            strategy = TrendFollowingStrategy(ticker, mode=mode)
            if strategy.load_data():
                trades = strategy.run_backtest(initial_capital=1000000, position_ratio=0.8)
                
                # 保存交易信号到CSV
                strategy.save_trades_to_csv()
                
                # 生成回测图表
                stock_dir = os.path.join(DATA_DIR, ticker)
                os.makedirs(stock_dir, exist_ok=True)
                plot_path = os.path.join(stock_dir, f"{ticker}_backtest_{timestamp}.png")
                strategy.plot_results(save_path=plot_path)
                
                if trades and len(trades) > 0:
                    profits = [t['profit'] for t in trades]
                    win_trades = [t for t in trades if t['profit'] > 0]
                    
                    result = {
                        'ticker': ticker,
                        'total_trades': len(trades),
                        'win_rate': len(win_trades) / len(trades) * 100,
                        'avg_profit': np.mean(profits),
                        'max_profit': max(profits),
                        'max_loss': min(profits),
                        'total_return': (strategy.data['portfolio_value'].iloc[-1] - 1000000) / 1000000 * 100,
                        'final_value': strategy.data['portfolio_value'].iloc[-1],
                        'stop_loss_count': sum(1 for t in trades if t['type'] == 'stop_loss'),
                        'trailing_stop_count': sum(1 for t in trades if t['type'] == 'trailing_stop'),
                        'trend_end_count': sum(1 for t in trades if t['type'] == 'trend_end')
                    }
                    results.append(result)
                    
                    print(f"总收益率: {result['total_return']:.2f}%")
                    print(f"交易次数: {result['total_trades']}")
                    print(f"胜率: {result['win_rate']:.2f}%")
                else:
                    print("无交易信号")
            else:
                print("加载数据失败")
        except Exception as e:
            print(f"分析失败: {str(e)}")
    
    return results

def analyze_results(results):
    """分析回测结果"""
    if not results:
        print("没有回测结果")
        return
    
    df = pd.DataFrame(results)
    
    print("\n" + "="*80)
    print("📊 批量回测结果统计")
    print("="*80)
    
    # 整体统计
    print(f"\n总股票数: {len(df)}")
    print(f"盈利股票数: {len(df[df['total_return'] > 0])} ({len(df[df['total_return'] > 0])/len(df)*100:.1f}%)")
    print(f"平均收益率: {df['total_return'].mean():.2f}%")
    print(f"平均胜率: {df['win_rate'].mean():.2f}%")
    print(f"平均交易次数: {df['total_trades'].mean():.1f}")
    
    # 表现最好的股票
    top_stocks = df.sort_values('total_return', ascending=False).head(5)
    print("\n🏆 表现最佳的5只股票:")
    for _, row in top_stocks.iterrows():
        print(f"  {row['ticker']}: 收益率 {row['total_return']:.2f}%, 胜率 {row['win_rate']:.1f}%, 交易 {int(row['total_trades'])}次")
    
    # 表现最差的股票
    worst_stocks = df.sort_values('total_return').head(5)
    print("\n💀 表现最差的5只股票:")
    for _, row in worst_stocks.iterrows():
        print(f"  {row['ticker']}: 收益率 {row['total_return']:.2f}%, 胜率 {row['win_rate']:.1f}%, 交易 {int(row['total_trades'])}次")
    
    # 离场类型分析
    print("\n📈 离场类型分布:")
    total_stop_loss = df['stop_loss_count'].sum()
    total_trailing = df['trailing_stop_count'].sum()
    total_trend_end = df['trend_end_count'].sum()
    total = total_stop_loss + total_trailing + total_trend_end
    
    if total > 0:
        print(f"  止损离场: {total_stop_loss}次 ({total_stop_loss/total*100:.1f}%)")
        print(f"  移动止盈: {total_trailing}次 ({total_trailing/total*100:.1f}%)")
        print(f"  趋势结束: {total_trend_end}次 ({total_trend_end/total*100:.1f}%)")
    
    # 策略有效性分析
    profitable = df[df['total_return'] > 0]
    avg_profit_win = profitable['avg_profit'].mean()
    avg_loss_lose = df[df['total_return'] <= 0]['avg_profit'].mean()
    
    print(f"\n📊 盈亏比分析:")
    print(f"  盈利股票平均收益: {avg_profit_win:.2f}%")
    print(f"  亏损股票平均亏损: {avg_loss_lose:.2f}%")
    
    # 保存结果到CSV
    timestamp = pd.Timestamp.now().strftime('%Y%m%d')
    result_path = os.path.join(DATA_DIR, f"backtest_results_{timestamp}.csv")
    df.to_csv(result_path, index=False, encoding='utf-8-sig')
    print(f"\n📁 结果已保存到: {result_path}")
    
    return df

def generate_suggestions(df):
    """生成优化建议"""
    print("\n" + "="*80)
    print("💡 策略优化建议")
    print("="*80)
    
    # 基于结果分析给出建议
    avg_win_rate = df['win_rate'].mean()
    avg_return = df['total_return'].mean()
    
    suggestions = []
    
    if avg_win_rate < 40:
        suggestions.append("⚠️ 胜率偏低(<40%)，建议：")
        suggestions.append("   - 提高ADX入场阈值，过滤弱趋势")
        suggestions.append("   - 增加量能要求，确保突破有效性")
        suggestions.append("   - 缩短趋势确认天数，减少延迟")
    
    if avg_return < 50:
        suggestions.append("\n⚠️ 整体收益偏低，建议：")
        suggestions.append("   - 优化止损参数，减少不必要的止损")
        suggestions.append("   - 调整移动止盈参数，让利润奔跑")
        suggestions.append("   - 考虑多时间周期确认")
    
    # 检查是否有股票表现特别好
    top_performer = df.sort_values('total_return', ascending=False).iloc[0]
    if top_performer['total_return'] > 100:
        suggestions.append(f"\n⭐ 优秀案例: {top_performer['ticker']}")
        suggestions.append(f"   - 收益率: {top_performer['total_return']:.2f}%")
        suggestions.append(f"   - 胜率: {top_performer['win_rate']:.1f}%")
        suggestions.append("   - 分析该股票特征，推广到其他股票")
    
    # 检查是否有股票表现特别差
    worst_performer = df.sort_values('total_return').iloc[0]
    if worst_performer['total_return'] < -30:
        suggestions.append(f"\n💀 问题案例: {worst_performer['ticker']}")
        suggestions.append(f"   - 收益率: {worst_performer['total_return']:.2f}%")
        suggestions.append(f"   - 交易次数: {int(worst_performer['total_trades'])}")
        suggestions.append("   - 分析失败原因，调整参数")
    
    for suggestion in suggestions:
        print(suggestion)

def generate_monitor_report(stocks):
    """生成监控报告，方便实时监控"""
    print("\n" + "="*80)
    print("📡 实时监控报告")
    print("="*80)
    
    holding_stocks = []
    pending_stocks = []
    timestamp = datetime.now().strftime('%Y%m%d')
    
    for ticker in stocks:
        stock_dir = os.path.join(DATA_DIR, ticker)
        
        # 优先查找今天的回测文件
        today_csv = f"{ticker}_backtest_{timestamp}.csv"
        csv_path = os.path.join(stock_dir, today_csv)
        
        if not os.path.exists(csv_path):
            # 如果今天的文件不存在，查找最新的回测文件（排除simplified版本）
            csv_files = []
            for f in os.listdir(stock_dir):
                if f.startswith(f"{ticker}_backtest_") and f.endswith(".csv") and "simplified" not in f:
                    csv_files.append(f)
            
            if csv_files:
                csv_files.sort()
                latest_csv = csv_files[-1]
                csv_path = os.path.join(stock_dir, latest_csv)
                print(f"⚠️  {ticker}: 未找到今日回测文件，使用最新文件: {latest_csv}")
            else:
                print(f"⚠️  {ticker}: 未找到回测文件")
                continue
        
        try:
            df = pd.read_csv(csv_path)
            
            if len(df) > 0:
                last_row = df.iloc[-1]
                signal_type = last_row['signal_type']
                exit_type = last_row['exit_type']
                
                if signal_type == 'sell':
                    if exit_type == 'final_close':
                        # final_close 表示持有到最后，仍在持仓中
                        buy_signals = df[df['signal_type'] == 'buy']
                        if len(buy_signals) > 0:
                            last_buy = buy_signals.iloc[-1]
                            holding_stocks.append({
                                'ticker': ticker,
                                'entry_date': last_buy['date'],
                                'entry_price': last_buy['price'],
                                'current_price': last_row['price'],
                                'profit': last_row['trade_profit'],
                                'ADX': last_row['ADX'],
                                'MACD_hist': last_row['MACD_hist'],
                                'trend_ended': last_row['trend_ended']
                            })
                        else:
                            # 没有对应的buy信号，按等待入场处理
                            pending_stocks.append({
                                'ticker': ticker,
                                'last_exit_date': last_row['date'],
                                'last_exit_type': exit_type,
                                'last_profit': last_row['trade_profit']
                            })
                    else:
                        # 非final_close的sell表示已离场，等待入场
                        pending_stocks.append({
                            'ticker': ticker,
                            'last_exit_date': last_row['date'],
                            'last_exit_type': exit_type,
                            'last_profit': last_row['trade_profit']
                        })
                elif signal_type == 'buy':
                    # 最后信号是buy，表示当前持有
                    holding_stocks.append({
                        'ticker': ticker,
                        'entry_date': last_row['date'],
                        'entry_price': last_row['price'],
                        'current_price': last_row['price'],
                        'profit': 0,
                        'ADX': last_row['ADX'],
                        'MACD_hist': last_row['MACD_hist'],
                        'trend_ended': last_row['trend_ended']
                    })
                else:
                    # 没有明确的买卖信号，按等待入场处理
                    pending_stocks.append({
                        'ticker': ticker,
                        'last_exit_date': last_row['date'] if 'date' in last_row else 'N/A',
                        'last_exit_type': 'unknown',
                        'last_profit': 0
                    })
        except Exception as e:
            print(f"❌ {ticker}: 读取回测文件失败 - {str(e)}")
    
    # 排序：持仓股票按买入日期降序，等待入场按上次离场日期降序
    holding_stocks.sort(key=lambda x: x['entry_date'], reverse=True)
    pending_stocks.sort(key=lambda x: x['last_exit_date'], reverse=True)
    
    print(f"\n📊 当前持仓股票 ({len(holding_stocks)}只):")
    print("-" * 120)
    print(f"{'股票代码':<12} {'买入日期':<12} {'买入价':<10} {'当前价':<10} {'收益(%)':<12} {'ADX':<8} {'MACD':<12} {'趋势结束':<10}")
    print("-" * 120)
    
    for stock in holding_stocks:
        trend_status = "否" if stock['trend_ended'] == 0 else "是"
        print(f"{stock['ticker']:<12} {stock['entry_date']:<12} {stock['entry_price']:<10.2f} {stock['current_price']:<10.2f} {stock['profit']:<12.2f} {stock['ADX']:<8.2f} {stock['MACD_hist']:<12.6f} {trend_status:<10}")
    
    print(f"\n📉 等待入场股票 ({len(pending_stocks)}只):")
    print("-" * 80)
    print(f"{'股票代码':<12} {'上次离场日期':<12} {'离场类型':<12} {'上次收益(%)':<12}")
    print("-" * 80)
    
    for stock in pending_stocks:
        print(f"{stock['ticker']:<12} {stock['last_exit_date']:<12} {stock['last_exit_type']:<12} {stock['last_profit']:<12.2f}")
    
    # 生成监控文件（MD格式）
    timestamp = datetime.now().strftime('%Y%m%d')
    monitor_file = os.path.join(DATA_DIR, f"monitor_report_{timestamp}.md")
    
    with open(monitor_file, 'w', encoding='utf-8') as f:
        f.write(f"# 📡 实时监控报告\n\n")
        f.write(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write(f"## 📊 当前持仓股票 ({len(holding_stocks)}只)\n\n")
        f.write(f"| 股票代码 | 买入日期 | 买入价 | 当前价 | 收益(%) | ADX | MACD_hist | 趋势结束 |\n")
        f.write(f"| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |\n")
        for stock in holding_stocks:
            trend_status = "否" if stock['trend_ended'] == 0 else "是"
            f.write(f"| {stock['ticker']} | {stock['entry_date']} | {stock['entry_price']:.2f} | {stock['current_price']:.2f} | {stock['profit']:.2f} | {stock['ADX']:.2f} | {stock['MACD_hist']:.6f} | {trend_status} |\n")
        
        f.write(f"\n## 📉 等待入场股票 ({len(pending_stocks)}只)\n\n")
        f.write(f"| 股票代码 | 上次离场日期 | 离场类型 | 上次收益(%) |\n")
        f.write(f"| :--- | :--- | :--- | :---: |\n")
        for stock in pending_stocks:
            f.write(f"| {stock['ticker']} | {stock['last_exit_date']} | {stock['last_exit_type']} | {stock['last_profit']:.2f} |\n")
    
    print(f"\n📁 监控报告已保存到: {monitor_file}")

def Glob(pattern, path):
    """简单的glob实现"""
    import fnmatch
    matches = []
    if os.path.exists(path):
        for filename in os.listdir(path):
            if fnmatch.fnmatch(filename, pattern):
                matches.append(filename)
    return matches

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="批量回测所有股票")
    parser.add_argument('--mode', choices=['full', 'simple'], default='full', help='策略模式')
    args = parser.parse_args()

    results = run_batch_backtest(mode=args.mode)
    df = analyze_results(results)
    generate_suggestions(df)
    stocks = get_all_stocks()
    generate_monitor_report(stocks)
