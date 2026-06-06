
# web_ui.py
# 股票分析Web界面
import os
import sys
from flask import Flask, render_template, request, jsonify, send_file

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)

# 导入API模块
from api.analysis import analysis_bp
from api.trading import trading_bp
from api.detailed import detailed_bp
from api.report_viewer import report_viewer_bp
from api.quick_analysis import quick_analysis_bp
from api.backtest import backtest_bp
from api.sector import sector_bp

# 注册蓝图
app.register_blueprint(analysis_bp, url_prefix='/api')
app.register_blueprint(trading_bp, url_prefix='/api')
app.register_blueprint(detailed_bp, url_prefix='/api')
app.register_blueprint(report_viewer_bp, url_prefix='/api')
app.register_blueprint(quick_analysis_bp, url_prefix='/api')
app.register_blueprint(backtest_bp, url_prefix='/api/backtest')
app.register_blueprint(sector_bp, url_prefix='/api')

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081, debug=True)
