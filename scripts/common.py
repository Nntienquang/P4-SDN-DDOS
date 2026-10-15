"""
common.py — Tiện ích dùng chung: đọc YAML/JSON, đường dẫn, logging nhẹ.

Có fallback đọc YAML tối giản nếu máy chưa cài PyYAML, để newbie không bị
chặn ở bước cài đặt. Khuyến nghị vẫn cài: pip install pyyaml.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _strip_comment(line):
    """Bỏ comment '#' ở ngoài chuỗi/flow. Giữ '#' trong '...' hoặc {..}/[..]."""
    out, depth, q = "", 0, None
    for ch in line:
        if q:
            out += ch
            if ch == q:
                q = None
            continue
        if ch in "'\"":
            q = ch; out += ch; continue
        if ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        if ch == "#" and depth == 0:
            break
        out += ch
    return out.rstrip()


def _tiny_yaml(text):
    """Parser YAML tối giản: key: value, dict lồng, và list '- ' (kể cả flow
    '{...}'/'[...]'). Có lookahead để phân biệt dict con và list con. Chỉ đủ cho
    config của repo này; khuyến nghị cài PyYAML để dùng đầy đủ."""
    lines = []
    for raw in text.splitlines():
        s = _strip_comment(raw)
        if s.strip():
            lines.append((len(s) - len(s.lstrip()), s.strip()))

    root = {}
    stack = [(-1, root)]

    def parent():
        return stack[-1][1]

    i = 0
    while i < len(lines):
        indent, line = lines[i]
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        p = parent()

        if line.startswith("- "):
            val = _coerce(line[2:].strip())
            if not isinstance(p, list):
                raise ValueError("YAML: list sai chỗ gần %r" % line)
            p.append(val)
            i += 1
            continue

        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val == "":
            # nhìn dòng kế để biết con là list hay dict
            child = {}
            if i + 1 < len(lines):
                nxt_indent, nxt = lines[i + 1]
                if nxt_indent > indent and nxt.startswith("- "):
                    child = []
            p[key] = child
            stack.append((indent, child))
        else:
            p[key] = _coerce(val)
        i += 1
    return root


def _split_top(s):
    """Tách theo dấu phẩy ở mức ngoài cùng (bỏ qua phẩy trong {} hoặc [])."""
    parts, depth, cur = [], 0, ""
    for ch in s:
        if ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur); cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


def _coerce(v):
    v = v.strip()
    # flow mapping {k: v, ...}
    if v.startswith("{") and v.endswith("}"):
        d = {}
        for item in _split_top(v[1:-1]):
            k, _, val = item.partition(":")
            d[k.strip()] = _coerce(val.strip())
        return d
    # flow sequence [a, b, ...]
    if v.startswith("[") and v.endswith("]"):
        return [_coerce(x) for x in _split_top(v[1:-1])]
    if v.startswith(("'", '"')) and v.endswith(("'", '"')):
        return v[1:-1]
    low = v.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "~", "none"):
        return None
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v


def load_yaml(path):
    with open(path) as f:
        text = f.read()
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text)
    except ModuleNotFoundError:
        return _tiny_yaml(text)


def load_json(path):
    with open(path) as f:
        return json.load(f)


def save_json(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path
