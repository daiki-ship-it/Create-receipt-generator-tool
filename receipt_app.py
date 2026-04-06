#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
領収書生成Webアプリ
起動: python3 receipt_app.py
"""

import io
import json
import os
import threading
import webbrowser
import urllib.parse
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.colors import black, HexColor

# 日本語フォント登録
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
FONT = 'HeiseiKakuGo-W5'

PAGE_W, PAGE_H = A4

# ──────────────────────────────────────────────────────────
# 発行者情報（変更する場合はここを編集してください）
# ──────────────────────────────────────────────────────────
ISSUER_NAME     = '佐藤 大生'
ISSUER_ADDRESS  = '〒362-0076 埼玉県上尾市弁財2丁目9番22-2号 ボンスヴェニールII 202'
ISSUER_EMAIL    = 'daiki@aiessences.com'
DEFAULT_PURPOSE = 'AIセミナー参加費（講師：佐藤大生）として'
# ──────────────────────────────────────────────────────────

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'receipt_history.json')


# ──────────────────────────────────────────────────────────
# 履歴管理
# ──────────────────────────────────────────────────────────

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_to_history(entry):
    history = load_history()
    history.insert(0, entry)   # 新しい順
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# ──────────────────────────────────────────────────────────
# HTML
# ──────────────────────────────────────────────────────────

HTML_PAGE = '''<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>領収書生成</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: -apple-system, "Hiragino Sans", sans-serif;
      background: #f0f2f5;
      margin: 0;
      padding: 40px 20px 60px;
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    h1 {
      font-size: 26px;
      color: #1a1a2e;
      margin-bottom: 30px;
      letter-spacing: 4px;
    }

    /* ── フォームカード ── */
    .card {
      background: white;
      border-radius: 14px;
      padding: 36px 40px;
      width: 100%;
      max-width: 480px;
      box-shadow: 0 4px 24px rgba(0,0,0,0.10);
    }
    label {
      display: block;
      font-size: 13px;
      font-weight: 600;
      color: #555;
      margin-bottom: 6px;
      margin-top: 18px;
    }
    label:first-of-type { margin-top: 0; }
    input[type="text"],
    input[type="date"],
    input[type="number"] {
      width: 100%;
      padding: 11px 14px;
      border: 1.5px solid #ddd;
      border-radius: 8px;
      font-size: 15px;
      color: #222;
      transition: border-color 0.2s, box-shadow 0.2s;
    }
    input:focus {
      outline: none;
      border-color: #2563eb;
      box-shadow: 0 0 0 3px rgba(37,99,235,0.12);
    }
    .row { display: flex; gap: 12px; }
    .row > div { flex: 1; }
    .divider { border: none; border-top: 1px solid #eee; margin: 20px 0 4px; }
    .sub-label {
      font-size: 11px;
      color: #aaa;
      text-transform: uppercase;
      letter-spacing: 1px;
      margin-top: 18px;
      margin-bottom: 6px;
    }
    #submit-btn {
      width: 100%;
      margin-top: 28px;
      padding: 14px;
      background: #2563eb;
      color: white;
      border: none;
      border-radius: 8px;
      font-size: 16px;
      font-weight: 600;
      cursor: pointer;
      letter-spacing: 1px;
      transition: background 0.2s, opacity 0.2s;
    }
    #submit-btn:hover:not(:disabled) { background: #1d4ed8; }
    #submit-btn:disabled { opacity: 0.6; cursor: not-allowed; }
    .note { text-align: center; margin-top: 12px; color: #888; font-size: 12px; }

    /* ── 成功トースト ── */
    #toast {
      display: none;
      align-items: center;
      gap: 8px;
      background: #16a34a;
      color: white;
      padding: 12px 20px;
      border-radius: 8px;
      margin-top: 16px;
      font-size: 14px;
      font-weight: 500;
      width: 100%;
      max-width: 480px;
    }

    /* ── 履歴 ── */
    .history-wrap {
      width: 100%;
      max-width: 860px;
      margin-top: 40px;
    }
    .history-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 14px;
    }
    .history-header h2 {
      font-size: 16px;
      color: #333;
      margin: 0;
      letter-spacing: 1px;
    }
    .badge {
      background: #e0e7ff;
      color: #3730a3;
      font-size: 12px;
      font-weight: 600;
      padding: 3px 10px;
      border-radius: 20px;
    }
    .history-empty {
      background: white;
      border-radius: 12px;
      padding: 36px;
      text-align: center;
      color: #aaa;
      font-size: 14px;
      box-shadow: 0 2px 12px rgba(0,0,0,0.07);
    }
    .history-table-wrap {
      background: white;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 2px 12px rgba(0,0,0,0.07);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }
    thead tr {
      background: #f8fafc;
      border-bottom: 2px solid #e5e7eb;
    }
    th {
      padding: 12px 16px;
      text-align: left;
      font-size: 12px;
      font-weight: 600;
      color: #6b7280;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      white-space: nowrap;
    }
    tbody tr {
      border-bottom: 1px solid #f1f5f9;
      transition: background 0.15s;
    }
    tbody tr:last-child { border-bottom: none; }
    tbody tr:hover { background: #f8fafc; }
    td {
      padding: 13px 16px;
      color: #374151;
      vertical-align: middle;
    }
    td.no   { font-family: monospace; font-size: 13px; color: #6b7280; }
    td.name { font-weight: 600; }
    td.amount { font-weight: 600; color: #1e40af; white-space: nowrap; }
    td.purpose { color: #6b7280; font-size: 13px; }
    .issued-at { display: block; font-size: 11px; color: #9ca3af; margin-top: 2px; }
    .del-btn, .dl-btn {
      border-radius: 6px;
      padding: 4px 10px;
      font-size: 12px;
      cursor: pointer;
      transition: background 0.15s, color 0.15s;
    }
    .dl-btn {
      background: none;
      border: 1px solid #93c5fd;
      color: #2563eb;
    }
    .dl-btn:hover { background: #2563eb; color: white; }
    .del-btn {
      background: none;
      border: 1px solid #fca5a5;
      color: #ef4444;
    }
    .del-btn:hover { background: #ef4444; color: white; }
    .action-btns { display: flex; gap: 6px; justify-content: flex-end; }
  </style>
</head>
<body>
  <h1>領　収　書　生　成</h1>

  <!-- フォーム -->
  <div class="card">
    <form id="receipt-form">
      <label>受取人名</label>
      <input id="inp-name" type="text" name="name" placeholder="例：木本 涼太" required autofocus>

      <label>領収日</label>
      <input id="inp-date" type="date" name="date" required>

      <div class="row">
        <div>
          <label>金額（税込・円）</label>
          <input id="inp-amount" type="number" name="amount" placeholder="例：4000" min="1" required>
        </div>
        <div>
          <label>No. 連番</label>
          <input id="inp-seq" type="number" name="seq" value="1" min="1">
        </div>
      </div>

      <hr class="divider">
      <p class="sub-label">但し書き</p>
      <input id="inp-purpose" type="text" name="purpose" value="AIセミナー参加費（講師：佐藤大生）として">

      <button type="submit" id="submit-btn">↓ 領収書 PDF を生成・ダウンロード</button>
    </form>
    <p class="note">PDFが自動でダウンロードされます</p>
  </div>

  <!-- 成功トースト -->
  <div id="toast">✓ &nbsp;領収書を発行しました — ダウンロードを確認してください</div>

  <!-- 発行履歴 -->
  <div class="history-wrap">
    <div class="history-header">
      <h2>発行履歴</h2>
      <span class="badge" id="history-count">0 件</span>
    </div>
    <div id="history-body">
      <div class="history-empty">まだ発行履歴はありません</div>
    </div>
  </div>

  <script>
    // ── 初期化 ──────────────────────────────────────────────
    (function() {
      const d = new Date();
      document.getElementById('inp-date').value =
        d.getFullYear() + '-' +
        String(d.getMonth()+1).padStart(2,'0') + '-' +
        String(d.getDate()).padStart(2,'0');
    })();

    loadHistory();

    // ── フォーム送信 ─────────────────────────────────────────
    document.getElementById('receipt-form').addEventListener('submit', async function(e) {
      e.preventDefault();

      const btn = document.getElementById('submit-btn');
      btn.textContent = '生成中...';
      btn.disabled = true;

      const params = new URLSearchParams({
        name:    document.getElementById('inp-name').value.trim(),
        date:    document.getElementById('inp-date').value,
        amount:  document.getElementById('inp-amount').value,
        seq:     document.getElementById('inp-seq').value,
        purpose: document.getElementById('inp-purpose').value.trim()
      });

      try {
        const resp = await fetch('/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: params.toString()
        });

        if (!resp.ok) {
          const text = await resp.text();
          alert('エラー: ' + text);
          return;
        }

        // PDF ダウンロード
        const blob = await resp.blob();
        const url  = URL.createObjectURL(blob);
        const a    = document.createElement('a');
        const cd   = resp.headers.get('Content-Disposition') || '';
        const m    = cd.match(/filename\*=UTF-8''(.+)/);
        a.download = m ? decodeURIComponent(m[1]) : '領収書.pdf';
        a.href = url;
        a.click();
        URL.revokeObjectURL(url);

        // フォームをクリア（日付・但し書きはそのまま）
        document.getElementById('inp-name').value   = '';
        document.getElementById('inp-amount').value = '';
        // No.連番を +1
        const seqEl = document.getElementById('inp-seq');
        seqEl.value = parseInt(seqEl.value || '1') + 1;

        // トースト表示
        showToast();

        // 履歴を更新
        await loadHistory();

        document.getElementById('inp-name').focus();

      } catch(err) {
        alert('エラー: ' + err);
      } finally {
        btn.textContent = '↓ 領収書 PDF を生成・ダウンロード';
        btn.disabled = false;
      }
    });

    // ── 成功トースト ─────────────────────────────────────────
    function showToast() {
      const t = document.getElementById('toast');
      t.style.display = 'flex';
      setTimeout(() => { t.style.display = 'none'; }, 3500);
    }

    // ── 履歴読み込み & 描画 ──────────────────────────────────
    async function loadHistory() {
      try {
        const resp = await fetch('/history');
        const data = await resp.json();
        renderHistory(data);
      } catch(_) {}
    }

    async function redownload(index) {
      const resp = await fetch('/redownload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'index=' + index
      });
      if (!resp.ok) { alert('エラー: ' + await resp.text()); return; }
      const blob = await resp.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      const cd   = resp.headers.get('Content-Disposition') || '';
      const m    = cd.match(/filename\*=UTF-8''(.+)/);
      a.download = m ? decodeURIComponent(m[1]) : '領収書.pdf';
      a.href = url;
      a.click();
      URL.revokeObjectURL(url);
    }

    async function deleteEntry(index) {
      if (!confirm('この履歴を削除しますか？')) return;
      await fetch('/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'index=' + index
      });
      await loadHistory();
    }

    function renderHistory(list) {
      document.getElementById('history-count').textContent = list.length + ' 件';

      const body = document.getElementById('history-body');
      if (!list.length) {
        body.innerHTML = '<div class="history-empty">まだ発行履歴はありません</div>';
        return;
      }

      const rows = list.map((h, i) => {
        const amt = Number(h.amount).toLocaleString('ja-JP');
        return `<tr id="row-${i}">
          <td class="no">${h.receipt_no}</td>
          <td>${h.date_display}<span class="issued-at">発行: ${h.issued_at}</span></td>
          <td class="name">${h.name}　様</td>
          <td class="amount">¥ ${amt}</td>
          <td class="purpose">${h.purpose}</td>
          <td><div class="action-btns">
            <button class="dl-btn"  onclick="redownload(${i})">再ダウンロード</button>
            <button class="del-btn" onclick="deleteEntry(${i})">削除</button>
          </div></td>
        </tr>`;
      }).join('');

      body.innerHTML = `
        <div class="history-table-wrap">
          <table>
            <thead>
              <tr>
                <th>No.</th>
                <th>領収日 / 発行日時</th>
                <th>受取人</th>
                <th>金額（税込）</th>
                <th>但し書き</th>
                <th></th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>`;
    }
  </script>
</body>
</html>'''


# ──────────────────────────────────────────────────────────
# PDF 生成
# ──────────────────────────────────────────────────────────

def calc_tax(total):
    pre_tax = round(total / 1.1)
    tax = total - pre_tax
    return pre_tax, tax


def generate_receipt_pdf(name, date_str, amount, seq_num=1, purpose=DEFAULT_PURPOSE):
    date         = datetime.strptime(date_str, '%Y-%m-%d')
    date_display = f'{date.year}年{date.month}月{date.day}日'
    receipt_no   = f"{date.strftime('%Y-%m-%d')}-{seq_num}"
    pre_tax, tax = calc_tax(amount)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    L = 25 * mm
    R = PAGE_W - 20 * mm

    # タイトル
    c.setFont(FONT, 22)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 35 * mm, '領　収　書')

    # No.
    c.setFont(FONT, 10)
    c.drawRightString(R, PAGE_H - 58 * mm, f'No. {receipt_no}')

    # 領収日
    c.drawRightString(R, PAGE_H - 68 * mm, f'領収日：{date_display}')

    # 受取人名
    name_y    = PAGE_H - 86 * mm
    name_disp = f'{name}＿様'
    c.setFont(FONT, 16)
    c.drawString(L, name_y, name_disp)
    tw = c.stringWidth(name_disp, FONT, 16)
    c.setLineWidth(1.3)
    c.line(L, name_y - 2, L + tw, name_y - 2)
    c.setLineWidth(1)

    # 金額ボックス
    box_h = 13 * mm
    box_w = 130 * mm
    box_x = (PAGE_W - box_w) / 2
    box_y = PAGE_H - 106 * mm

    c.setFillColor(HexColor('#C8C8C8'))
    c.setStrokeColor(black)
    c.setLineWidth(1.5)
    c.rect(box_x, box_y, box_w, box_h, fill=1, stroke=1)
    c.setFillColor(black)
    c.setLineWidth(1)

    c.setFont(FONT, 13)
    c.drawCentredString(PAGE_W / 2, box_y + 4 * mm,
                        f'金　額　　¥ {amount:,} -　（税込）')

    # 但し書き
    but_y = box_y - 16 * mm
    c.setFont(FONT, 10)
    c.drawString(L, but_y, f'但　{purpose}')

    # 受領確認文
    c.drawString(L, but_y - 10 * mm, '上記金額、正に受領いたしました。')

    # 内訳
    section_y = but_y - 25 * mm
    c.drawString(L, section_y, '内訳')

    table_top = section_y - 6 * mm
    table_w   = R - L
    col1_w    = table_w * 0.4
    col2_w    = table_w * 0.6
    row_h     = 10 * mm

    c.setFillColor(HexColor('#E0E0E0'))
    c.rect(L, table_top - row_h, table_w, row_h, fill=1, stroke=1)
    c.setFillColor(black)
    c.setFont(FONT, 10)
    c.drawCentredString(L + col1_w / 2,          table_top - row_h + 3.5 * mm, '項目')
    c.drawCentredString(L + col1_w + col2_w / 2, table_top - row_h + 3.5 * mm, '金額')
    c.line(L + col1_w, table_top, L + col1_w, table_top - row_h)

    r1 = table_top - row_h
    c.rect(L, r1 - row_h, table_w, row_h, fill=0, stroke=1)
    c.drawCentredString(L + col1_w / 2,          r1 - row_h + 3.5 * mm, '税抜金額')
    c.drawCentredString(L + col1_w + col2_w / 2, r1 - row_h + 3.5 * mm, f'¥ {pre_tax:,}')
    c.line(L + col1_w, r1, L + col1_w, r1 - row_h)

    r2 = r1 - row_h
    c.rect(L, r2 - row_h, table_w, row_h, fill=0, stroke=1)
    c.drawCentredString(L + col1_w / 2,          r2 - row_h + 3.5 * mm, '消費税額(10%)')
    c.drawCentredString(L + col1_w + col2_w / 2, r2 - row_h + 3.5 * mm, f'¥ {tax:,}')
    c.line(L + col1_w, r2, L + col1_w, r2 - row_h)

    # 発行者
    issuer_y = r2 - 3.5 * row_h
    sp = 9 * mm
    c.setFont(FONT, 10)
    c.drawString(L, issuer_y,          '【発行者】')
    c.drawString(L, issuer_y - sp,     f'氏名：{ISSUER_NAME}')
    c.drawString(L, issuer_y - 2 * sp, f'住所：{ISSUER_ADDRESS}')
    c.drawString(L, issuer_y - 3 * sp, f'連絡先：{ISSUER_EMAIL}')
    c.drawString(L, issuer_y - 4.5*sp,
                 '※本領収書をPDF等の電子データで発行する場合、印紙税は課税されません。')

    c.save()
    return buf.getvalue()


# ──────────────────────────────────────────────────────────
# HTTP ハンドラ
# ──────────────────────────────────────────────────────────

class ReceiptHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == '/history':
            data = json.dumps(load_history(), ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            page = HTML_PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(page)))
            self.end_headers()
            self.wfile.write(page)

    def do_POST(self):
        if self.path == '/redownload':
            try:
                length  = int(self.headers.get('Content-Length', 0))
                body    = self.rfile.read(length).decode('utf-8')
                data    = urllib.parse.parse_qs(body)
                index   = int(data.get('index', ['0'])[0])
                history = load_history()
                if index < 0 or index >= len(history):
                    return self._error('履歴が見つかりません')
                h = history[index]
                seq_num = int(h['receipt_no'].rsplit('-', 1)[-1])
                pdf_bytes = generate_receipt_pdf(
                    h['name'], h['date'], h['amount'], seq_num, h['purpose'])
                safe_name = urllib.parse.quote(f"領収書_{h['name']}.pdf", safe='')
                self.send_response(200)
                self.send_header('Content-Type', 'application/pdf')
                self.send_header('Content-Disposition',
                                 f"attachment; filename*=UTF-8''{safe_name}")
                self.send_header('Content-Length', str(len(pdf_bytes)))
                self.end_headers()
                self.wfile.write(pdf_bytes)
            except Exception as e:
                self._error(f'エラー: {e}')
            return

        if self.path == '/delete':
            try:
                length = int(self.headers.get('Content-Length', 0))
                body   = self.rfile.read(length).decode('utf-8')
                data   = urllib.parse.parse_qs(body)
                index  = int(data.get('index', ['0'])[0])
                history = load_history()
                if 0 <= index < len(history):
                    history.pop(index)
                    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                        json.dump(history, f, ensure_ascii=False, indent=2)
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'ok')
            except Exception as e:
                self._error(f'エラー: {e}')
            return

        if self.path != '/generate':
            self._error('Not found', 404)
            return
        try:
            length   = int(self.headers.get('Content-Length', 0))
            body     = self.rfile.read(length).decode('utf-8')
            data     = urllib.parse.parse_qs(body)

            name     = data.get('name',    [''])[0].strip()
            date_str = data.get('date',    [''])[0].strip()
            amount   = int(data.get('amount', ['0'])[0].strip())
            seq_num  = int(data.get('seq',    ['1'])[0].strip() or '1')
            purpose  = (data.get('purpose', [DEFAULT_PURPOSE])[0].strip()
                        or DEFAULT_PURPOSE)

            if not name or not date_str or not amount:
                return self._error('名前・領収日・金額は必須です。')

            pdf_bytes = generate_receipt_pdf(name, date_str, amount, seq_num, purpose)

            # 履歴に保存
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            save_to_history({
                'receipt_no':  f"{date_str}-{seq_num}",
                'issued_at':   datetime.now().strftime('%Y-%m-%d %H:%M'),
                'name':        name,
                'date':        date_str,
                'date_display': f'{date_obj.year}年{date_obj.month}月{date_obj.day}日',
                'amount':      amount,
                'purpose':     purpose,
            })

            safe_name = urllib.parse.quote(f'領収書_{name}.pdf', safe='')
            self.send_response(200)
            self.send_header('Content-Type', 'application/pdf')
            self.send_header('Content-Disposition',
                             f"attachment; filename*=UTF-8''{safe_name}")
            self.send_header('Content-Length', str(len(pdf_bytes)))
            self.end_headers()
            self.wfile.write(pdf_bytes)

        except Exception as e:
            self._error(f'エラー: {e}')

    def _error(self, msg, code=400):
        body = msg.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ──────────────────────────────────────────────────────────
# 起動
# ──────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-browser', action='store_true',
                        help='起動時にブラウザを開かない（バックグラウンド起動用）')
    args = parser.parse_args()

    server = None
    for p in range(8765, 8775):
        try:
            server = HTTPServer(('127.0.0.1', p), ReceiptHandler)
            break
        except OSError:
            continue

    if not server:
        print('ポートが見つかりませんでした。')
        return

    url = f'http://localhost:{server.server_address[1]}'
    print(f'\n  領収書生成アプリ起動中')
    print(f'  URL: {url}')
    print(f'  終了: Ctrl+C\n')

    if not args.no_browser:
        def open_browser():
            import time
            time.sleep(0.6)
            webbrowser.open(url)
        threading.Thread(target=open_browser, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nアプリを終了しました。')


if __name__ == '__main__':
    main()
