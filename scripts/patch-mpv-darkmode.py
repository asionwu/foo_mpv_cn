#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修补 mpv 源码：避免 libmpv 嵌入宿主时污染宿主的深色模式。

背景
----
mpv 的 `video/out/w32_common.c` 里 `update_dark_mode()` 会调用
`uxtheme!SetPreferredAppMode(1)`（未公开 API，序号 135，**进程级**），
目的是让自己的窗口能使用深色标题栏。

但该 API 作用于**整个进程**。当 libmpv 被宿主程序（如 foobar2000）加载时，
这次调用会把宿主设置的 `ForceDark(2)` 覆盖成 `AllowDark(1)`；
若系统处于浅色主题，宿主整个界面（含右键菜单）就会变浅色。

修法
----
加上 `!w32->parent` 条件 —— 仅在 mpv 自建顶层窗口（独立运行）时调用；
嵌入模式（`wid` 或桌面嵌入）下 `parent` 非空，跳过调用。
窗口级的 `SetWindowTheme` / `DwmSetWindowAttribute` 不受影响，
所以 mpv 自身窗口的深色表现保持不变。

用法
----
    python3 scripts/patch-mpv-darkmode.py <mpv 源码目录>

不带参数时使用当前目录。脚本是**幂等**的；找不到目标代码时
以非零退出码结束，避免静默跳过导致补丁失效而无人察觉。
"""
import pathlib
import re
import sys

MARKER = 'if (!w32->parent && w32->api.pSetPreferredAppMode)'

PATTERN = re.compile(
    r'(?P<ind>[ \t]*)if \(w32->api\.pSetPreferredAppMode\)\n'
    r'(?P=ind)[ \t]*w32->api\.pSetPreferredAppMode\(1\);[^\n]*')


def main() -> int:
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '.')
    path = root / 'video' / 'out' / 'w32_common.c'
    if not path.is_file():
        print('错误：找不到 %s' % path, file=sys.stderr)
        return 2

    src = path.read_text(encoding='utf-8')

    if MARKER in src:
        print('已打过补丁，跳过：%s' % path)
        return 0

    m = PATTERN.search(src)
    if not m:
        print('错误：未找到目标代码，mpv 上游可能已改动：%s' % path, file=sys.stderr)
        return 3

    ind = m.group('ind')
    repl = (
        '{i}// foo_mpv: SetPreferredAppMode 是进程级 API。libmpv 嵌入宿主\n'
        '{i}// （如 foobar2000）时调用会覆盖宿主的深色模式设置\n'
        '{i}// （ForceDark 被降级为 AllowDark），导致宿主界面变浅色。\n'
        '{i}// 仅在 mpv 自建顶层窗口（非嵌入）时才启用。\n'
        '{i}if (!w32->parent && w32->api.pSetPreferredAppMode)\n'
        '{i}    w32->api.pSetPreferredAppMode(1); // allow dark mode'
    ).format(i=ind)

    out = src[:m.start()] + repl + src[m.end():]

    # 自检：括号配平 + 替换确实生效
    if out.count('{') != out.count('}'):
        print('错误：替换后大括号不配平，放弃写入', file=sys.stderr)
        return 4
    if MARKER not in out:
        print('错误：替换未生效，放弃写入', file=sys.stderr)
        return 5

    path.write_text(out, encoding='utf-8')
    print('已修补：%s' % path)
    print('（%s）' % MARKER)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
