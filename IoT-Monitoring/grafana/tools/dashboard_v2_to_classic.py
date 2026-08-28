#!/usr/bin/env python3
"""
dashboard_v2_to_classic.py — Grafana 13 UI 내보내기(v2 스키마)를 프로비저닝용 classic 스키마로 변환.

Grafana 13 의 "Export → JSON" 은 새 스키마(v2: elements/layout/kind/spec)로 나오는데,
**파일 프로비저닝은 classic 스키마(panels + schemaVersion + uid)만 읽는다.**
v2 를 그대로 넣으면 대시보드가 로드되지 않아 빈 화면이 된다.

사용:
  python dashboard_v2_to_classic.py a.json                      # 미리보기(표준출력)
  python dashboard_v2_to_classic.py a.json --uid iot-monitoring \
      -o ../provisioning/dashboards/iot-monitoring.json

입력이 이미 classic 이면 그대로 통과시킨다(안전).
"""
import argparse
import json
import sys

HIDE_MAP = {"dontHide": 0, "hideLabel": 1, "hideVariable": 2}

VAR_KIND_MAP = {
    "CustomVariable": "custom",
    "QueryVariable": "query",
    "ConstantVariable": "constant",
    "TextVariable": "textbox",
    "IntervalVariable": "interval",
    "DatasourceVariable": "datasource",
}


def q_to_target(pq):
    """PanelQuery -> classic target. 데이터소스별 쿼리 본문(spec)은 그대로 옮긴다."""
    spec = pq.get("spec", {})
    q = spec.get("query", {})
    t = dict(q.get("spec", {}))
    t["refId"] = spec.get("refId", "A")
    if spec.get("hidden"):
        t["hide"] = True
    ds = q.get("datasource") or {}
    if ds.get("name"):
        t["datasource"] = {"type": q.get("group"), "uid": ds["name"]}
    return t


def element_to_panel(name, el, grid):
    """v2 element + GridLayoutItem 좌표 -> classic panel"""
    s = el.get("spec", {})
    viz = s.get("vizConfig", {})
    vspec = viz.get("spec", {})
    data = (s.get("data") or {}).get("spec", {})
    queries = data.get("queries", [])

    try:
        fallback_id = int(str(name).rsplit("-", 1)[-1])
    except ValueError:
        fallback_id = 0

    panel = {
        "id": s.get("id") or fallback_id,
        "type": viz.get("group"),                 # v2 는 패널 타입을 vizConfig.group 에 둔다
        "title": s.get("title", ""),
        "gridPos": {"h": grid["h"], "w": grid["w"], "x": grid["x"], "y": grid["y"]},
        "fieldConfig": vspec.get("fieldConfig", {"defaults": {}, "overrides": []}),
        "options": vspec.get("options", {}),
    }
    if s.get("description"):
        panel["description"] = s["description"]
    if s.get("links"):
        panel["links"] = s["links"]
    if queries:
        panel["targets"] = [q_to_target(q) for q in queries]
        first = (queries[0].get("spec") or {}).get("query") or {}
        if (first.get("datasource") or {}).get("name"):
            panel["datasource"] = {"type": first.get("group"),
                                   "uid": first["datasource"]["name"]}
    if data.get("transformations"):
        panel["transformations"] = data["transformations"]
    return panel


def grid_items(layout):
    """GridLayout -> [(element_name, {x,y,w,h})]"""
    out = []
    for it in (layout.get("spec", {}) or {}).get("items", []):
        sp = it.get("spec", {})
        ref = (sp.get("element") or {}).get("name")
        if ref:
            out.append((ref, {"x": sp.get("x", 0), "y": sp.get("y", 0),
                              "w": sp.get("width", 12), "h": sp.get("height", 8)}))
    return out


def var_to_classic(v):
    s = v.get("spec", {})
    cur = s.get("current", {}) or {}
    out = {
        "type": VAR_KIND_MAP.get(v.get("kind", ""), "custom"),
        "name": s.get("name"),
        "label": s.get("label"),
        "hide": HIDE_MAP.get(s.get("hide"), 0),
        "skipUrlSync": s.get("skipUrlSync", False),
        "current": {"text": cur.get("text"), "value": cur.get("value")},
        "options": s.get("options", []) or [],
        "query": s.get("query", ""),
        "multi": s.get("multi", False),
        "includeAll": s.get("includeAll", False),
    }
    # custom 변수는 "표시 : 값, ..." 질의 문자열에서 options 를 복원해 둔다
    if out["type"] == "custom" and not out["options"] and out["query"]:
        opts = []
        for part in str(out["query"]).split(","):
            part = part.strip()
            if not part:
                continue
            if " : " in part:
                text, val = part.split(" : ", 1)
            else:
                text = val = part
            opts.append({"selected": val.strip() == out["current"]["value"],
                         "text": text.strip(), "value": val.strip()})
        out["options"] = opts
    return out


def convert(v2, uid=None):
    els = v2.get("elements", {})
    panels = []
    y_cursor = 0
    next_row_id = 10000

    rows = (v2.get("layout", {}).get("spec", {}) or {}).get("rows")
    if rows is None:                       # RowsLayout 이 아니면 단일 GridLayout 으로 취급
        rows = [{"spec": {"title": "", "hideHeader": True, "layout": v2.get("layout", {})}}]

    for row in rows:
        rs = row.get("spec", {})
        items = grid_items(rs.get("layout", {}))
        has_header = not rs.get("hideHeader", False)
        row_panel = None

        if has_header:                     # classic 의 row 패널로 표현
            row_panel = {
                "id": next_row_id,
                "type": "row",
                "title": rs.get("title", ""),
                "collapsed": bool(rs.get("collapse", False)),
                "gridPos": {"h": 1, "w": 24, "x": 0, "y": y_cursor},
                "panels": [],
            }
            next_row_id += 1
            y_cursor += 1

        inner = []
        max_bottom = y_cursor
        for ref, g in items:
            el = els.get(ref)
            if not el:
                continue
            g = dict(g)
            g["y"] = g["y"] + y_cursor
            inner.append(element_to_panel(ref, el, g))
            max_bottom = max(max_bottom, g["y"] + g["h"])

        if row_panel is not None:
            if row_panel["collapsed"]:
                row_panel["panels"] = inner        # 접힌 행은 패널을 안에 중첩
                panels.append(row_panel)
                y_cursor += 1
            else:
                panels.append(row_panel)
                panels.extend(inner)
                y_cursor = max_bottom
        else:
            panels.extend(inner)
            y_cursor = max_bottom

    ts = v2.get("timeSettings", {}) or {}
    return {
        "annotations": {"list": []},
        "editable": v2.get("editable", True),
        "fiscalYearStartMonth": ts.get("fiscalYearStartMonth", 0),
        "graphTooltip": 0,
        "links": v2.get("links", []),
        "panels": panels,
        "preload": v2.get("preload", False),
        "refresh": ts.get("autoRefresh", ""),
        "schemaVersion": 41,
        "tags": v2.get("tags", []),
        "templating": {"list": [var_to_classic(v) for v in v2.get("variables", [])]},
        "time": {"from": ts.get("from", "now-6h"), "to": ts.get("to", "now")},
        "timepicker": {},
        "timezone": ts.get("timezone", "browser"),
        "title": v2.get("title", "Dashboard"),
        "uid": uid or v2.get("uid") or "",
        "version": 1,
    }


def main():
    ap = argparse.ArgumentParser(description="Grafana v2 대시보드 JSON -> classic 변환")
    ap.add_argument("input")
    ap.add_argument("-o", "--out", help="저장 경로 (없으면 표준출력)")
    ap.add_argument("--uid", help="classic 의 uid (프로비저닝에 필요)")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as f:
        d = json.load(f)

    # Grafana 13 의 "Export as code" 는 쿠버네티스 스타일 래퍼로 나온다:
    #   { apiVersion: dashboard.grafana.app/v2, kind: Dashboard, metadata: {...}, spec: {...} }
    # 실제 대시보드는 spec 안에 있으므로 벗겨낸다.
    if d.get("kind") == "Dashboard" and isinstance(d.get("spec"), dict):
        meta = d.get("metadata") or {}
        sys.stderr.write("[래퍼] %s 감지 - spec 을 사용합니다 (metadata.name=%s)\n"
                         % (d.get("apiVersion"), meta.get("name")))
        if not args.uid and meta.get("name"):
            args.uid = meta["name"]
        d = d["spec"]

    if "panels" in d and "elements" not in d:
        sys.stderr.write("[정보] 이미 classic 스키마입니다 - 그대로 통과시킵니다.\n")
        out = d
        if args.uid:
            out["uid"] = args.uid
    else:
        out = convert(d, args.uid)
        sys.stderr.write("[변환] 패널 %d개 - 변수 %d개 - uid=%s\n"
                         % (len(out["panels"]), len(out["templating"]["list"]),
                            out["uid"] or "(없음)"))
        if not out["uid"]:
            sys.stderr.write("[경고] uid 가 비었습니다. --uid 로 지정하세요 (예: --uid iot-monitoring)\n")

    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        sys.stderr.write("[저장] %s\n" % args.out)
    else:
        print(text)


if __name__ == "__main__":
    main()
