
# web_ui.py
# 股票分析Web界面
import os
import sys
from flask import Flask, render_template, request, jsonify, send_file, make_response

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
    # 前端是单页面，浏览器可能缓存旧 HTML/JS，导致改版后刷新仍看到旧界面。
    response = make_response(render_template('index.html'))
    response.headers['Cache-Control'] = 'no-store, must-revalidate'
    return response


def _parse_bool(value):
    """解析环境变量中的布尔值。"""
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def get_run_config():
    """读取 Web 服务监听配置，返回 (host, port, debug)。

    默认只监听本机 127.0.0.1 且关闭调试模式，避免把服务暴露到局域网；
    需要覆盖时设置环境变量 GP_ANA_WEB_HOST / GP_ANA_WEB_DEBUG。
    """
    host = os.environ.get('GP_ANA_WEB_HOST', '127.0.0.1').strip() or '127.0.0.1'
    debug = _parse_bool(os.environ.get('GP_ANA_WEB_DEBUG', ''))
    return host, 8081, debug


if __name__ == '__main__':
    run_host, run_port, run_debug = get_run_config()
    # 项目按 Python 3.10/3.11 的依赖锁定（numpy 1.26 等）；用更高版本解释器起服务时，
    # 子进程会用同一个解释器跑指标/回测，容易踩依赖或数值口径差异，这里显式提示。
    if sys.version_info >= (3, 12):
        print(f"⚠️  当前解释器是 Python {sys.version.split()[0]}，项目按 3.10/3.11 验证。")
        print("   建议改用：/opt/anaconda3/envs/codex/bin/python web_ui.py")
    print(f"股票分析 Web 界面：http://{run_host}:{run_port}（debug={run_debug}）")
    if run_host in ('0.0.0.0', '::'):
        print("提示：当前监听所有网卡，局域网内其他设备可以访问该服务")
    app.run(host=run_host, port=run_port, debug=run_debug)
