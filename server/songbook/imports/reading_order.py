"""Conservative gutter-based reading order for positioned words."""


def order_columns(words: list[dict], width: float) -> list[dict]:
    if not words:
        return []
    candidates = []
    for step in range(25, 76):
        gutter = width * step / 100
        left = [w for w in words if w["x1"] <= gutter]
        right = [w for w in words if w["x0"] >= gutter]
        crossing = [w for w in words if w["x0"] < gutter < w["x1"]]
        if len(left) < 2 or len(right) < 2:
            continue
        if max(min(w["top"] for w in left), min(w["top"] for w in right)) > min(
            max(w["bottom"] for w in left), max(w["bottom"] for w in right)
        ):
            continue
        clearance = min(
            gutter - max(w["x1"] for w in left), min(w["x0"] for w in right) - gutter
        )
        candidates.append(
            (
                len(crossing),
                -clearance,
                abs(gutter - width / 2),
                gutter,
                left,
                right,
                crossing,
            )
        )
    if not candidates:
        return sorted(words, key=lambda w: (w["top"], w["x0"]))
    crossings, neg_clearance, _, gutter, left, right, crossing = min(
        candidates, key=lambda x: x[:3]
    )
    if crossings > max(1, len(words) // 12) or -neg_clearance < width * 0.025:
        return sorted(words, key=lambda w: (w["top"], w["x0"]))
    body_top = min(w["top"] for w in left + right)
    if any(w["bottom"] > body_top for w in crossing):
        return sorted(words, key=lambda w: (w["top"], w["x0"]))
    key = lambda w: (w["top"], w["x0"])
    if left and right:
        first_body = max(min(w["top"] for w in left), min(w["top"] for w in right))
        intro = [
            w
            for w in left + right
            if w["bottom"] <= first_body
            and w["x0"] > width * 0.2
            and w["x1"] < width * 0.8
        ]
        left = [w for w in left if w not in intro]
        right = [w for w in right if w not in intro]
        crossing += intro
    return sorted(crossing, key=key) + sorted(left, key=key) + sorted(right, key=key)
