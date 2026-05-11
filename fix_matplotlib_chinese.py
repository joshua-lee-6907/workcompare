#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复 Windows 下 matplotlib 中文显示方框问题。
功能：
1) 查找可用中文字体（优先微软雅黑）
2) 写入 matplotlibrc（用户级）
3) 清理字体缓存
4) 生成中文测试图 test_chinese_font.png
"""

import os
import shutil
from pathlib import Path
import matplotlib
from matplotlib import font_manager as fm

PREFERRED = [
    "Microsoft YaHei", "SimHei", "SimSun", "NSimSun", "KaiTi", "FangSong",
    "Noto Sans CJK SC", "WenQuanYi Zen Hei"
]


def pick_font_name() -> str:
    available = {f.name for f in fm.fontManager.ttflist}
    for name in PREFERRED:
        if name in available:
            return name
    return "DejaVu Sans"


def write_user_matplotlibrc(font_name: str) -> Path:
    cfg_dir = Path(matplotlib.get_configdir())
    cfg_dir.mkdir(parents=True, exist_ok=True)
    rc_path = cfg_dir / "matplotlibrc"
    content = (
        "font.family: sans-serif\n"
        f"font.sans-serif: {font_name}, SimHei, Microsoft YaHei, Noto Sans CJK SC, DejaVu Sans\n"
        "axes.unicode_minus: False\n"
    )
    rc_path.write_text(content, encoding="utf-8")
    return rc_path


def clear_font_cache() -> None:
    cache_dir = Path(matplotlib.get_cachedir())
    if cache_dir.exists():
        for p in cache_dir.glob("fontlist-v*.json"):
            try:
                p.unlink()
            except Exception:
                pass


def make_test_plot(font_name: str) -> Path:
    import matplotlib.pyplot as plt
    from matplotlib import rcParams

    rcParams["font.family"] = "sans-serif"
    rcParams["font.sans-serif"] = [font_name, "SimHei", "Microsoft YaHei", "Noto Sans CJK SC", "DejaVu Sans"]
    rcParams["axes.unicode_minus"] = False

    x = [0, 1, 2, 3, 4]
    y = [1, 3, 2, 5, 4]
    plt.figure(figsize=(8, 4))
    plt.plot(x, y, marker="o")
    plt.title("中文显示测试：温度（℃）与压力（kPa）")
    plt.xlabel("时间（s）")
    plt.ylabel("数据值")
    plt.grid(True, alpha=0.3)
    out = Path.cwd() / "test_chinese_font.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    return out


def main() -> None:
    font_name = pick_font_name()
    rc_path = write_user_matplotlibrc(font_name)
    clear_font_cache()
    img = make_test_plot(font_name)
    print(f"[OK] 已选择字体: {font_name}")
    print(f"[OK] 已写入配置: {rc_path}")
    print(f"[OK] 已清理字体缓存: {matplotlib.get_cachedir()}")
    print(f"[OK] 已生成测试图: {img}")
    print("\n请重启你的 Python/IDE 后再运行绘图程序。")


if __name__ == "__main__":
    main()
