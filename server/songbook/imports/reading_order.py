"""Conservative gutter-based reading order for positioned words."""


def order_columns(words: list[dict], width: float) -> list[dict]:
    if not words:
        return []
    spanning = [word for word in words if word["x1"] - word["x0"] > width * 0.45]
    body = [word for word in words if word not in spanning]
    if not body:
        return sorted(words, key=lambda word: (word["top"], word["x0"]))
    ordered_x = sorted(body, key=lambda word: word["x0"])
    edge = ordered_x[0]["x1"]
    gaps = []
    for word in ordered_x[1:]:
        if word["x0"] > edge:
            gaps.append((word["x0"] - edge, (word["x0"] + edge) / 2))
        edge = max(edge, word["x1"])
    valid = [
        (size, x)
        for size, x in gaps
        if size >= width * 0.08 and width * 0.2 < x < width * 0.8
    ]
    if not valid:
        return sorted(words, key=lambda word: (word["top"], word["x0"]))
    _, gutter = max(valid)
    if spanning and max(word["bottom"] for word in spanning) <= min(
        word["top"] for word in body
    ):
        return sorted(spanning, key=lambda word: (word["top"], word["x0"])) + sorted(
            body, key=lambda word: (word["x0"] >= gutter, word["top"], word["x0"])
        )
    return sorted(
        words, key=lambda word: (word["x0"] >= gutter, word["top"], word["x0"])
    )
