"""Tables with a per-row copy-as-JSON button (handy for pasting into an LLM)."""

import html
import json
import math
from datetime import date, datetime

import pandas as pd
import streamlit.components.v1 as components

PCT_HINTS = {
    "change_pct", "ema_distance_pct", "backtest_return", "backtest_vs_hold", "total_return",
    "benchmark_return", "excess_return", "cagr", "max_drawdown", "win_rate", "exposure",
    "avg_forward_return", "hit_rate", "return_pct", "drawdown", "pnl_pct",
}


def _raw(value):
    """JSON-safe value at full precision."""
    if value is None or (isinstance(value, float) and math.isnan(value)) or value is pd.NaT:
        return None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if hasattr(value, "item"):
        return _raw(value.item())
    if isinstance(value, float) and math.isinf(value):
        return None
    return value


def _display(col: str, value, pct_cols: set) -> str:
    value = _raw(value)
    if value is None:
        return "-"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        if col in pct_cols:
            return f"{value * 100:.2f}%"
        if isinstance(value, int):
            return f"{value:,}"
        return f"{value:,.4f}" if abs(value) < 100 else f"{value:,.2f}"
    text = str(value)
    if len(text) >= 19 and text[4] == "-" and text[10] == "T":
        return text.replace("T", " ", 1)
    return text


CSS = """
<style>
body{margin:0;font:13px -apple-system,Segoe UI,Roboto,sans-serif;color:#31333f;background:transparent}
.bar{display:flex;justify-content:flex-end;margin-bottom:4px}
.wrap{overflow:auto;border:1px solid rgba(128,128,128,.3);border-radius:6px}
table{border-collapse:collapse;width:100%}
th,td{padding:5px 8px;text-align:left;white-space:nowrap;border-bottom:1px solid rgba(128,128,128,.15)}
th{position:sticky;top:0;background:#f0f2f6;cursor:pointer;user-select:none}
td.n{text-align:right}
button{cursor:pointer;border:1px solid rgba(128,128,128,.4);background:transparent;color:inherit;border-radius:4px;padding:2px 6px}
button:hover{background:rgba(128,128,128,.2)}
button.ok{background:#2e7d32;color:#fff}
@media (prefers-color-scheme: dark){body{color:#fafafa}th{background:#262730}}
</style>
"""

JS = """
<script>
function copyText(text, btn, label){
  const done=()=>{const o=btn.textContent;btn.textContent=label||'✓';btn.classList.add('ok');
    setTimeout(()=>{btn.textContent=o;btn.classList.remove('ok')},1200)};
  const fallback=()=>{const t=document.createElement('textarea');t.value=text;document.body.appendChild(t);
    t.select();try{document.execCommand('copy')}catch(e){}document.body.removeChild(t);done()};
  if(navigator.clipboard&&window.isSecureContext){navigator.clipboard.writeText(text).then(done,fallback)}else{fallback()}
}
function copyRow(btn){copyText(btn.closest('tr').dataset.json,btn)}
function copyAll(btn){
  const rows=[...document.querySelectorAll('tbody tr')].map(r=>JSON.parse(r.dataset.json));
  copyText(JSON.stringify(rows,null,2),btn,'Copied ✓')
}
function sortBy(i,th){
  const tb=document.querySelector('tbody');const rows=[...tb.rows];
  const dir=th.dataset.dir==='asc'?-1:1;th.dataset.dir=dir===1?'asc':'desc';
  const key=r=>{const v=JSON.parse(r.dataset.json);return Object.values(v)[i-1]};
  rows.sort((a,b)=>{const x=key(a),y=key(b);
    if(x===null)return 1;if(y===null)return -1;
    return (x>y?1:x<y?-1:0)*dir});
  rows.forEach(r=>tb.appendChild(r));
}
</script>
"""


def copyable_table(df: pd.DataFrame, height: int | None = None, pct_cols: set | None = None) -> None:
    """Render ``df`` with a 📋 button per row copying that row as JSON, plus 'Copy all'."""
    if df is None or df.empty:
        components.html("<i style='font:13px sans-serif'>No rows.</i>", height=30)
        return
    df = df.reset_index(drop=df.index.name is None and isinstance(df.index, pd.RangeIndex))
    cols = list(df.columns)
    pcts = (set(pct_cols) if pct_cols is not None else set()) | (PCT_HINTS & set(map(str, cols)))

    head = "<th></th>" + "".join(
        f"<th onclick='sortBy({i + 1},this)'>{html.escape(str(c))}</th>" for i, c in enumerate(cols)
    )
    body = []
    for _, row in df.iterrows():
        raw = {str(c): _raw(row[c]) for c in cols}
        payload = html.escape(json.dumps(raw, default=str), quote=True)
        cells = "".join(
            f"<td class='{'n' if isinstance(_raw(row[c]), (int, float)) and not isinstance(_raw(row[c]), bool) else ''}'>"
            f"{html.escape(_display(str(c), row[c], pcts))}</td>"
            for c in cols
        )
        body.append(f"<tr data-json=\"{payload}\"><td><button title='Copy row as JSON' onclick='copyRow(this)'>📋</button></td>{cells}</tr>")

    page = (
        CSS
        + "<div class='bar'><button onclick='copyAll(this)'>📋 Copy all as JSON</button></div>"
        + f"<div class='wrap' style='max-height:{(height or 420) - 40}px'><table><thead><tr>{head}</tr></thead>"
        + f"<tbody>{''.join(body)}</tbody></table></div>"
        + JS
    )
    auto = 40 + 34 * (len(df) + 1)
    components.html(page, height=min(height or 420, auto + 10), scrolling=False)
