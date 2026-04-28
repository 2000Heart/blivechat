# -*- coding: utf-8 -*-
"""从已登录浏览器获取 live.douyin.com Cookie 的说明与小书签（供管理界面使用）。"""
from __future__ import annotations

from urllib.parse import quote

DOUYIN_LIVE_URL = 'https://live.douyin.com/'

# 在 live.douyin.com 任意页面点击该书签：复制 document.cookie 到剪贴板（不含 HttpOnly）。
_BOOKMARKLET_JS = (
    "(function(){var c=document.cookie||'';"
    "if(!c){alert('当前页 document.cookie 为空：可能未登录，或关键 Cookie 为 HttpOnly。"
    "请改用「开发者工具 → Network」复制请求头里的 Cookie 整行。');return;}"
    "function ok(){alert('已复制 '+c.length+' 字符。若礼物等仍失败，请用 Network 复制完整 Cookie（含 HttpOnly）。');}"
    "if(navigator.clipboard&&navigator.clipboard.writeText){"
    "navigator.clipboard.writeText(c).then(ok).catch(function(){prompt('请手动全选复制',c);});"
    "}else{prompt('请手动全选复制',c);}})();"
)


def bookmarklet_href() -> str:
    return 'javascript:' + quote(_BOOKMARKLET_JS, safe='')


COOKIE_HELP_TEXT = """获取 douyin_cookie 的两种方式

【方式一】小书签（最快，适合先试）
1. 在本窗口点「复制小书签链接」。
2. 浏览器新建书签，名称随意，网址/URL 处粘贴刚才复制的内容并保存。
3. 用同一浏览器打开并登录 https://live.douyin.com/ ，在直播页点击该书签。
4. 若提示已复制，将内容粘贴到本插件「抖音请求头或 Cookie」输入框，保存配置。

说明：小书签只能读取页面脚本可见的 Cookie，不含 HttpOnly。若接口仍缺权限，请用方式二。

【方式二】开发者工具（完整 Cookie，推荐）
1. 打开 https://live.douyin.com/ 并确认已登录。
2. 按 F12（或 右键 → 检查）打开开发者工具，切到 Network（网络）。
3. 刷新页面或点选列表中任意发往 live.douyin.com / webcast 的请求。
4. 在右侧 Headers / 标头 中找到 Request Headers 里的 Cookie: 一行，复制整行值（只要等号后面的长字符串即可；也可整段「Cookie: …」粘贴，本插件会解析）。
5. 粘贴到本插件输入框，保存配置。

安全提示：Cookie 等同登录凭证，勿发给他人或提交到公开仓库。"""
