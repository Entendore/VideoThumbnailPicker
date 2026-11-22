def format_time(t: float) -> str:
    m, s = divmod(int(t), 60)
    ms = int((t % 1) * 1000)
    return f"{m:02d}:{s:02d}.{ms:03d}"