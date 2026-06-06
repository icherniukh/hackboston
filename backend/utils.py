def srt_timestamp_to_mmssms(srt_ts: str) -> str:
    h, m, s_ms = srt_ts.split(":")
    s, ms = s_ms.split(",")
    total_min = int(h) * 60 + int(m)
    return f"{total_min:02d}:{s}:{ms}"


def float_seconds_to_mmssms(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    m, ms = divmod(total_ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{m:02d}:{s:02d}:{ms:03d}"


def mmssms_to_float_seconds(ts: str) -> float:
    m, s, ms = ts.split(":")
    return int(m) * 60 + int(s) + int(ms) / 1000
