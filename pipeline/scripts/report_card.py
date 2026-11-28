"""Builds the one-page report card (self-contained HTML) from the pipeline check results.
Plain Python, no Blender needed, so it can also be rebuilt from saved JSON.

    import report_card
    html_path = report_card.write(card, out_path)

`card` = {
  "name", "date", "stage", "hero", "group", "height_cm", "verdict",
  "sections": [ {"title", "verdict", "checks": [ {status, check, detail, pose?} ], "images": [path...],
                 "notes": [str]} ],
  "measured": {...}, "entry": {...}
}
"""
import base64
import html
import json
import os

ORDER = {"ASK": 0, "FIX": 1, "FIXED": 2, "CHECK": 3, "INFO": 4, "PASS": 5}
CHIP = {"PASS": ("#2f6b3a", "#e3f1e5"), "ASK": ("#8a4b0f", "#fbecd9"), "FIX": ("#8a1f1f", "#f8e1e1"),
        "FIXED": ("#1f4f8a", "#e1ebf8"), "CHECK": ("#5b3f8a", "#ece5f6"), "INFO": ("#555", "#eee")}
PLAIN = {"PASS": "Passed", "ASK": "Needs your decision", "FIX": "Must be fixed",
         "FIXED": "Fixed automatically", "CHECK": "Look and confirm", "INFO": "Note"}


def _chip(status):
    fg, bg = CHIP.get(status, CHIP["INFO"])
    return f'<span class="chip" style="color:{fg};background:{bg}">{html.escape(PLAIN.get(status, status))}</span>'


def _img(path, max_bytes=2_500_000):
    if not path or not os.path.exists(path):
        return ""
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
    data = open(path, "rb").read()
    if len(data) > max_bytes:
        return f'<div class="missing">{html.escape(os.path.basename(path))} (too large to embed; next to this page)</div>'
    b64 = base64.b64encode(data).decode()
    cap = os.path.splitext(os.path.basename(path))[0].split("_", 1)[-1].replace("_", " ")
    return f'<figure><img src="data:{mime};base64,{b64}" alt="{html.escape(cap)}"><figcaption>{html.escape(cap)}</figcaption></figure>'


def verdict(statuses):
    if "FIX" in statuses:
        return "FIX"
    if "ASK" in statuses:
        return "ASK"
    if "CHECK" in statuses:
        return "CHECK"
    return "PASS"


CSS = """
body{font:15px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;color:#222;background:#f6f4ef;margin:0}
main{max-width:1100px;margin:0 auto;padding:28px 24px 60px}
h1{font-size:26px;margin:0 0 4px} h2{font-size:19px;margin:34px 0 10px;border-bottom:2px solid #e2ddd2;padding-bottom:6px}
.meta{color:#666;margin-bottom:18px}
.chip{display:inline-block;border-radius:999px;padding:2px 10px;font-size:12.5px;font-weight:600;white-space:nowrap}
.big{font-size:15px;padding:5px 14px}
.box{background:#fff;border:1px solid #e2ddd2;border-radius:10px;padding:14px 18px;margin:10px 0}
table{border-collapse:collapse;width:100%;font-size:14px}
td,th{padding:6px 8px;border-bottom:1px solid #eee;text-align:left;vertical-align:top}
th{color:#666;font-weight:600;font-size:12.5px;text-transform:uppercase;letter-spacing:.03em}
.q li{margin:6px 0}
.grid{display:flex;flex-wrap:wrap;gap:10px;margin-top:10px}
figure{margin:0;background:#3d3d3d;border-radius:8px;overflow:hidden;flex:1 1 220px;max-width:100%}
figure img{display:block;width:100%;height:auto}
figure.wide{flex-basis:100%}
figcaption{color:#ddd;font-size:12px;padding:4px 8px}
details summary{cursor:pointer;color:#555;margin:6px 0}
.missing{color:#999;font-size:13px}
.fb td{height:28px}
"""


def build(card):
    secs = card.get("sections", [])
    allc = [c for s in secs for c in s.get("checks", [])]
    ov = card.get("verdict") or verdict([c["status"] for c in allc])
    out = [f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>Report card: {html.escape(card['name'])}</title>"
           f"<style>{CSS}</style></head><body><main>"]
    out.append(f"<h1>{html.escape(card['name'])} — report card</h1>")
    meta = [card.get("date", ""), f"stage: {card.get('stage', '?')}",
            "hero" if card.get("hero") else "not a hero", card.get("group", ""),
            f"{card.get('height_cm', '?')} cm"]
    out.append(f"<div class='meta'>{' · '.join(html.escape(str(m)) for m in meta if m)}</div>")
    out.append(f"<div class='box'>Overall: {_chip(ov).replace('chip', 'chip big', 1)}"
               + "".join(f" &nbsp;{_chip(s['verdict'])} {html.escape(s['title'])}" for s in secs) + "</div>")

    qs = [c for c in allc if c["status"] in ("ASK", "FIX")]
    looks = [c for c in allc if c["status"] == "CHECK"]
    fixed = [c for c in allc if c["status"] == "FIXED"]
    out.append("<h2>For you to decide</h2>")
    if qs:
        out.append("<ol class='q'>" + "".join(
            f"<li>{_chip(c['status'])} <b>{html.escape(c['check'])}</b>"
            f"{' (' + html.escape(c['pose']) + ' pose)' if c.get('pose') and c['pose'] != 'rest' else ''}: "
            f"{html.escape(c['detail'])}</li>" for c in qs) + "</ol>")
    else:
        out.append("<p>Nothing needs a decision.</p>")
    if looks:
        out.append("<h2>Look at the pictures and confirm</h2><ul class='q'>" +
                   "".join(f"<li>☐ {html.escape(c['detail'])}</li>" for c in looks) + "</ul>")
    if fixed:
        out.append("<h2>Fixed automatically</h2><ul>" +
                   "".join(f"<li>{html.escape(c['check'])}: {html.escape(c['detail'])}</li>" for c in fixed) + "</ul>")

    for s in secs:
        out.append(f"<h2>{html.escape(s['title'])} &nbsp;{_chip(s['verdict'])}</h2>")
        for n in s.get("notes", []):
            out.append(f"<p>{html.escape(n)}</p>")
        imgs = s.get("images", [])
        if imgs:
            wide = s.get("wide_images", False)
            out.append("<div class='grid'>" + "".join(
                _img(p).replace("<figure>", "<figure class='wide'>") if wide else _img(p) for p in imgs) + "</div>")
        rows = sorted(s.get("checks", []), key=lambda c: ORDER.get(c["status"], 9))
        if rows:
            out.append("<details" + (" open" if s["verdict"] != "PASS" else "") + "><summary>All checks ("
                       f"{len(rows)})</summary><table><tr><th>Result</th><th>Check</th><th>Detail</th></tr>")
            for c in rows:
                pose = f" <span style='color:#888'>({html.escape(c['pose'])})</span>" if c.get("pose") else ""
                out.append(f"<tr><td>{_chip(c['status'])}</td><td>{html.escape(c['check'])}{pose}</td>"
                           f"<td>{html.escape(str(c['detail']))}</td></tr>")
            out.append("</table></details>")

    out.append("<h2>Your feedback (one round)</h2><div class='box'><p>Write each note as a one-off fix, or as an "
               "<b>always / never</b> rule for the style guide.</p><table class='fb'>"
               "<tr><th>Area</th><th>Note</th><th>One-off or rule?</th></tr>" +
               "".join(f"<tr><td>{a}</td><td></td><td></td></tr>" for a in
                       ("Face", "Colours", "Proportions", "Clothing / must-haves", "Hands & feet", "Movement", "Other"))
               + "</table></div>")
    m = card.get("measured")
    if m:
        out.append("<h2>Measurements</h2><details><summary>Show raw numbers</summary><pre>"
                   + html.escape(json.dumps(m, indent=2, default=str)) + "</pre></details>")
    out.append("</main></body></html>")
    return "\n".join(out)


def write(card, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(build(card))
    with open(os.path.splitext(path)[0] + ".json", "w", encoding="utf-8") as f:
        json.dump(card, f, indent=2, default=str)
    return path
