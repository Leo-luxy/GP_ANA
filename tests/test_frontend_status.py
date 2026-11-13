"""用Node执行真实轮询函数，确保降级不会显示绿色完成或残留旧持仓。"""
import json
import pathlib
import re
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which('node'), '需要Node验证前端轮询分支')
class FrontendStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (pathlib.Path(__file__).resolve().parents[1] / 'templates' / 'index.html').read_text()

    def run_branch(self, function_name, end_name, status):
        start = self.source.index('function ' + function_name + '(')
        end = self.source.index('function ' + end_name + '(', start)
        function = self.source[start:end]
        harness = """
const vm = require('node:vm');
const assert = require('node:assert/strict');
const target = {innerHTML: '', children: [], replaceChildren(child) {this.children=[child]; this.innerHTML=child.textContent;}};
const elements = new Map();
const context = {
 document: {getElementById: (id) => {if(!elements.has(id)) elements.set(id,target); return elements.get(id);},
            createElement: () => ({className:'',textContent:''})},
 fetch: () => Promise.resolve({json: () => Promise.resolve(STATUS)}),
 setTimeout: () => {},
 localStorage: {getItem: () => null, setItem: () => {}},
 loadSelectionResult: () => {target.loads = (target.loads || 0) + 1;}, loadBacktestReport: () => {}, loadBacktestStockList: () => {},
};
vm.createContext(context); vm.runInContext(SOURCE, context);
context[NAME]('test');
setImmediate(() => { console.log(JSON.stringify(target)); });
"""
        harness = harness.replace('STATUS', json.dumps(status)).replace('SOURCE', json.dumps(function)).replace('NAME', json.dumps(function_name))
        result = subprocess.run([shutil.which('node'), '-e', harness], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_selection_degraded_has_warning_not_success(self):
        result = self.run_branch('pollSelectionTaskStatus', 'loadSelectionResult',
                                 {'status':'degraded','degraded':True,'warnings':['部分失败']})
        self.assertEqual(result['children'][0]['className'], 'alert alert-warning')
        self.assertIn('名单只含已完成校验的股票', result['innerHTML'])
        self.assertNotIn('alert-success', result['innerHTML'])
        self.assertNotIn('任务不存在', result['innerHTML'])

    def test_selection_pending_keeps_polling(self):
        result = self.run_branch('pollSelectionTaskStatus', 'loadSelectionResult',
                                 {'status':'pending','progress':42,'progress_label':'（5/73 只）'})
        html = result['innerHTML']
        self.assertIn('progress', html)
        self.assertNotIn('任务不存在', html)
        # 必须有真实可见的进度条（带宽度、颜色、百分比与步骤标签）
        self.assertIn('progress-bar', html)
        self.assertIn('width: 42%', html)
        self.assertIn('background-color', html)
        self.assertIn('42%', html)
        self.assertIn('5/73', html)

    def test_backtest_completed_degraded_is_yellow(self):
        # 只执行函数本身，后续加载由harness模拟。
        start = self.source.index('function pollBacktestStatus(')
        next_function = re.search(r'function (\w+)\(', self.source[start + 10:])
        result = self.run_branch('pollBacktestStatus', next_function.group(1),
                                 {'status':'completed','degraded':True,'warnings':['数据缺失']})
        self.assertEqual(result['children'][0]['className'], 'alert alert-warning')
        self.assertNotIn('alert-success', result['innerHTML'])

    def test_backtest_failure_is_summary_with_collapsed_safe_log(self):
        result = self.run_branch('pollBacktestStatus', 'loadBacktestReport', {
            'status': 'failed', 'error_summary': '回测未完成，请检查数据',
            'messages': ['<img src=x onerror=alert(1)>', '源数据未达到期望交易日']})
        html = result['innerHTML']
        self.assertIn('回测未完成，请检查数据', html)
        self.assertIn('<details', html)
        self.assertNotIn('<details open', html)
        self.assertIn('max-height: 320px', html)
        self.assertNotIn('<img', html)
        self.assertIn('&lt;img', html)

    def test_chart_requests_bind_strategy_and_clear_stale_image(self):
        start = self.source.index('function loadBacktestStockList(')
        end = self.source.index('// ==================== 板块分析相关函数', start)
        functions = self.source[start:end]
        self.assertIn("get_stock_list?mode=", functions)
        self.assertIn("'?mode=' + encodeURIComponent(lastBacktestMode)", functions)
        self.assertIn("image.removeAttribute('src')", functions)

    def test_selection_date_columns_are_not_numeric_formatted(self):
        self.assertIn("col.includes('截止日')", self.source)
        self.assertIn("text.slice(0, 4) + '-' + text.slice(4, 6)", self.source)

    def test_selection_start_keeps_latest_saved_table(self):
        start = self.source.index('function runStockSelection(')
        end = self.source.index('function pollSelectionTaskStatus(', start)
        function = self.source[start:end]
        self.assertNotIn("getElementById('selection-result').style.display = 'none'", function)
        self.assertNotIn("getElementById('selection-result-content').textContent = ''", function)
        self.assertIn('loadSelectionResult()', function)
        start = self.source.index('function showStockSelection(')
        opened = self.source[start:self.source.index('function runStockSelection(', start)]
        self.assertIn('loadSelectionResult()', opened)
        failed = self.run_branch('pollSelectionTaskStatus', 'loadSelectionResult', {'status': 'failed'})
        self.assertEqual(failed['loads'], 1)


if __name__ == '__main__':
    unittest.main()
