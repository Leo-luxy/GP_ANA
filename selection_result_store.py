"""成功结果单文件原子保存；失败任务不能覆盖历史展示。"""
import hashlib
import json
import os
import uuid
from datetime import datetime


def saved_path(output_path):
    return os.path.splitext(output_path)[0] + '_latest_success.json'


def save_result(output_path, status):
    if not (status.get('completed') is True and status.get('valid') is True
            and status.get('void') is False and status.get('state') in ('completed', 'degraded')):
        return
    with open(output_path, 'rb') as fh:
        payload = fh.read()
    if hashlib.sha256(payload).hexdigest() != status.get('csv_sha256'):
        raise ValueError('历史结果保存失败：CSV指纹不匹配')
    bundle = dict(schema=1, status=dict(status), csv=payload.decode('utf-8-sig'))
    bundle['status']['csv_sha256'] = hashlib.sha256(bundle['csv'].encode('utf-8')).hexdigest()
    path = saved_path(output_path)
    tmp = path + '.' + uuid.uuid4().hex + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(bundle, fh, ensure_ascii=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def preserve_legacy_display(output_path):
    """旧版本已抹掉批次状态时，仅留展示副本，不制造成功批次身份。"""
    path = os.path.splitext(output_path)[0] + '_legacy_display.json'
    if os.path.exists(saved_path(output_path)) or os.path.exists(path) or not os.path.isfile(output_path):
        return
    with open(output_path, 'r', encoding='utf-8-sig') as fh:
        csv_text = fh.read()
    bundle = dict(schema=1, verified=False, csv=csv_text,
                  csv_sha256=hashlib.sha256(csv_text.encode('utf-8')).hexdigest())
    tmp = path + '.' + uuid.uuid4().hex + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(bundle, fh, ensure_ascii=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def history_dir(output_path):
    return os.path.join(os.path.dirname(os.path.abspath(output_path)), 'selection_history')


def archive_daily(output_path, status):
    """按交易日留存最终结果：未来复盘才知道当时预测准不准。

    同一天多次成功运行只保留最后一次（当日最终名单），
    另追加 runs.log 记录历次运行，避免覆盖掉审计痕迹。
    """
    if not (status.get('completed') is True and status.get('valid') is True
            and status.get('void') is False and status.get('state') in ('completed', 'degraded')):
        return None
    asof = str(status.get('data_asof') or '')
    if len(asof) != 8 or not asof.isdigit():
        return None
    with open(output_path, 'rb') as fh:
        payload = fh.read()
    if hashlib.sha256(payload).hexdigest() != status.get('csv_sha256'):
        raise ValueError('按日归档失败：CSV指纹不匹配')
    target = os.path.join(history_dir(output_path), asof)
    os.makedirs(target, exist_ok=True)
    run_id = uuid.uuid4().hex
    for name, data in ((f'final_holdings.{run_id}.csv', payload),
                       (f'status.{run_id}.json',
                        json.dumps(dict(status), ensure_ascii=False, indent=2).encode('utf-8'))):
        tmp = os.path.join(target, name + '.tmp')
        with open(tmp, 'wb') as fh:
            fh.write(data)
        os.replace(tmp, os.path.join(target, name))
    # 当日最终名单指向本次（最后一次）成功运行；历次运行文件保留，便于追查。
    for source, fixed in ((f'final_holdings.{run_id}.csv', 'final_holdings.csv'),
                          (f'status.{run_id}.json', 'status.json')):
        src = os.path.join(target, source)
        dst = os.path.join(target, fixed)
        tmp = dst + '.tmp'
        with open(src, 'rb') as fh, open(tmp, 'wb') as out:
            out.write(fh.read())
        os.replace(tmp, dst)
    record = dict(archived_at=datetime.now().isoformat(timespec='seconds'), run_id=run_id,
                  holdings=int(status.get('holdings') or 0),
                  processed=int(status.get('processed') or 0),
                  degraded=bool(status.get('degraded')),
                  csv_sha256=hashlib.sha256(payload).hexdigest())
    with open(os.path.join(target, 'runs.log'), 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + '\n')
    return target


def history_index(output_path):
    """返回可复盘的交易日列表（新的在前）。"""
    base = history_dir(output_path)
    if not os.path.isdir(base):
        return []
    items = []
    for name in sorted(os.listdir(base), reverse=True):
        folder = os.path.join(base, name)
        if not (len(name) == 8 and name.isdigit() and os.path.isdir(folder)):
            continue
        status_file = os.path.join(folder, 'status.json')
        runs = 0
        log = os.path.join(folder, 'runs.log')
        if os.path.isfile(log):
            with open(log, encoding='utf-8') as fh:
                runs = sum(1 for line in fh if line.strip())
        try:
            with open(status_file, encoding='utf-8') as fh:
                status = json.load(fh)
        except (OSError, ValueError):
            continue
        items.append(dict(date=name, holdings=status.get('holdings'),
                          verified=status.get('verified', True),
                          processed=status.get('processed'),
                          state=status.get('state'), degraded=bool(status.get('degraded')),
                          finished_at=status.get('finished_at') or status.get('generated_at'),
                          runs=runs, has_csv=os.path.isfile(os.path.join(folder, 'final_holdings.csv'))))
    return items


def read_history(output_path, date):
    """读取某天留存的最终名单，并核对内容指纹。"""
    if len(date) != 8 or not date.isdigit():
        raise ValueError('历史日期格式应为 YYYYMMDD')
    folder = os.path.join(history_dir(output_path), date)
    with open(os.path.join(folder, 'status.json'), encoding='utf-8') as fh:
        status = json.load(fh)
    with open(os.path.join(folder, 'final_holdings.csv'), 'rb') as fh:
        payload = fh.read()
    if hashlib.sha256(payload).hexdigest() != status.get('csv_sha256'):
        raise ValueError('历史名单与留存状态指纹不一致')
    return payload, status


def backfill_legacy(output_path):
    """把旧版本遗留的最终名单补录进按日历史，并显式标为未核验。

    只为不丢掉已有的复盘素材；这类记录不能与正常成功批次等同。
    """
    if not os.path.isfile(output_path):
        return None
    with open(output_path, 'r', encoding='utf-8-sig') as fh:
        text = fh.read()
    rows = [line for line in text.splitlines() if line.strip()]
    if len(rows) < 2:
        return None
    header = rows[0].split(',')
    if '数据截止日' not in header:
        return None
    index = header.index('数据截止日')
    dates = {line.split(',')[index].strip() for line in rows[1:]}
    if len(dates) != 1:
        return None
    asof = dates.pop()
    if len(asof) != 8 or not asof.isdigit():
        return None
    target = os.path.join(history_dir(output_path), asof)
    if os.path.isfile(os.path.join(target, 'status.json')):
        return None
    os.makedirs(target, exist_ok=True)
    payload = text.encode('utf-8')
    status = dict(schema=0, state='legacy', verified=False, void=False,
                  data_asof=asof, holdings=len(rows) - 1,
                  csv_sha256=hashlib.sha256(payload).hexdigest(),
                  finished_at=datetime.now().isoformat(timespec='seconds'))
    for name, data in (('final_holdings.csv', payload),
                       ('status.json', json.dumps(status, ensure_ascii=False, indent=2).encode('utf-8'))):
        tmp = os.path.join(target, name + '.tmp')
        with open(tmp, 'wb') as fh:
            fh.write(data)
        os.replace(tmp, os.path.join(target, name))
    return target


def preserve_existing(output_path, status_path):
    try:
        with open(status_path, encoding='utf-8') as fh:
            status = json.load(fh)
        save_result(output_path, status)
    except (OSError, ValueError, TypeError):
        pass  # 缺失旧批次身份时不能制造成功身份。
