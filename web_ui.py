
# web_ui.py
# 股票分析Web界面
import os
import sys
from flask import Flask, render_template, request, jsonify, send_file

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 网络代理守护：默认直连、不使用系统代理（子进程会继承该设置）
from net_guard import ensure_network_ready
ensure_network_ready()

app = Flask(__name__)

# 导入API模块
from api.analysis import analysis_bp
from api.trading import trading_bp
from api.detailed import detailed_bp
from api.report_viewer import report_viewer_bp
from api.quick_analysis import quick_analysis_bp
from api.backtest import backtest_bp
from api.sector import sector_bp
from api.stock_selection import stock_selection_bp
from api.watchlist import watchlist_bp

# 注册蓝图
app.register_blueprint(analysis_bp, url_prefix='/api')
app.register_blueprint(trading_bp, url_prefix='/api')
app.register_blueprint(detailed_bp, url_prefix='/api')
app.register_blueprint(report_viewer_bp, url_prefix='/api')
app.register_blueprint(quick_analysis_bp, url_prefix='/api')
app.register_blueprint(backtest_bp, url_prefix='/api/backtest')
app.register_blueprint(sector_bp, url_prefix='/api')
app.register_blueprint(stock_selection_bp, url_prefix='/api')
app.register_blueprint(watchlist_bp, url_prefix='/api')

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081, debug=True)
