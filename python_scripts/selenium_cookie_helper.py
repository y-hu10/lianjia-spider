#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
集成Selenium自动Cookie更新的爬虫
在检测到验证码时自动打开浏览器，等待用户验证后自动提取Cookie
"""

import json
import time
import re
from urllib.parse import urlparse
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium_stealth import stealth        # ① 引入 stealth
from logger import get_logger


class SeleniumCookieHelper:
    """Selenium Cookie辅助工具"""
    
    def __init__(self, browser='edge'):
        self.browser = browser
        self.logger = get_logger()
        self.driver = None

    def _get_cookie_bootstrap_url(self, url):
        """返回一个可注入 cookie 的同域引导页，避免目标页先加载一次后再刷新。"""
        parsed = urlparse(url)
        scheme = parsed.scheme or 'https'
        netloc = parsed.netloc
        return f"{scheme}://{netloc}/"

    def _is_blocked_page(self, page_source, current_url):
        """判断当前页面是否仍处于验证/拦截状态。"""
        blocked_markers = (
            'captcha',
            'verify',
            'security',
            '人机验证',
            '访问验证',
            '请输入验证码',
        )
        page_text = page_source.lower()
        url_text = current_url.lower()
        return any(marker in page_text or marker in url_text for marker in blocked_markers)

    def _inspect_page_state(self):
        """采集当前页面状态，避免仅凭 URL 或源码中的脚本片段误判。"""
        page_source = self.driver.page_source
        current_url = self.driver.current_url
        page_title = self.driver.title
        ready_state = self.driver.execute_script("return document.readyState")
        body_text = self.driver.execute_script(
            "return document.body ? (document.body.innerText || '') : '';"
        )
        frame_sources = self.driver.execute_script(
            """
            return Array.from(document.querySelectorAll('iframe'))
                .map(frame => frame.src || '')
                .filter(Boolean);
            """
        )

        body_text = body_text or ""
        visible_text = re.sub(r'\s+', ' ', body_text.lower())
        title_text = (page_title or "").lower()
        url_text = current_url.lower()
        frame_text = " ".join(frame_sources).lower()

        blocked_markers = (
            'captcha',
            'verify',
            'security',
            '人机验证',
            '访问验证',
            '请输入验证码',
            '请完成验证',
            '滑动验证',
        )
        blocked_hits = [
            marker for marker in blocked_markers
            if marker in visible_text or marker in title_text or marker in url_text or marker in frame_text
        ]
        has_verification_iframe = any(
            marker in frame_text for marker in ('captcha', 'verify', 'security', 'geetest', 'challenge')
        )

        has_page_content = self._has_meaningful_lianjia_content(
            page_source,
            current_url,
            page_title,
            body_text,
        )
        # 验证脚本/iframe 可能在正常页面中残留，只有在正文内容不足时才视为仍被拦截。
        is_blocked = bool(blocked_hits or has_verification_iframe) and not has_page_content

        return {
            'page_source': page_source,
            'current_url': current_url,
            'page_title': page_title,
            'ready_state': ready_state,
            'body_text': body_text,
            'is_blocked': is_blocked,
            'blocked_hits': blocked_hits,
            'has_verification_iframe': has_verification_iframe,
            'has_page_content': has_page_content,
            'body_length': len(body_text.strip()),
        }

    def _has_meaningful_lianjia_content(self, page_source, current_url, page_title, body_text):
        """使用较宽松的启发式判断是否已回到可用的链家页面。"""
        current_url_lower = current_url.lower()
        title_text = (page_title or "").lower()
        normalized_source = page_source.lower()
        normalized_body = re.sub(r'\s+', ' ', (body_text or '').lower())

        known_page_markers = (
            'selllistcontent',
            'page-box fr',
            'totalsellcount',
            'content__list',
            'data-lj_action',
            'ershoufang-detail',
            'm-content',
        )
        content_keywords = (
            '二手房',
            '房源',
            '总价',
            '单价',
            '关注',
            '带看',
            '链家',
        )

        has_known_marker = any(marker in normalized_source for marker in known_page_markers)
        has_real_url = 'lianjia.com' in current_url_lower and '/ershoufang/' in current_url_lower
        has_real_title = any(keyword in page_title for keyword in ('二手房', '房源', '链家'))
        has_real_text = len(normalized_body) >= 200 and any(
            keyword.lower() in normalized_body for keyword in content_keywords
        )

        return has_known_marker or (has_real_url and (has_real_title or has_real_text))

    def _is_page_ready(self):
        """检测页面是否完成加载且已离开验证码页。"""
        page_state = self._inspect_page_state()
        return (
            page_state['ready_state'] in ('interactive', 'complete') and
            page_state['has_page_content'] and
            not page_state['is_blocked']
        )
    
    def open_for_manual_verification(self, url, current_cookies, wait_seconds=60):
        """
        打开浏览器供用户手动验证，然后自动提取Cookie
        
        Args:
            url: 要访问的URL
            wait_seconds: 等待用户验证的秒数（0=无限等待）
            
        Returns:
            包含 Cookie、当前页面 HTML 和最终 URL 的字典
        """
        try:
            self.logger.info("🌐 正在启动浏览器...")
            
            # 创建浏览器
            options = ChromeOptions()
            # 不使用无头模式，让用户可以看到浏览器
            options.add_argument('--start-maximized')
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            
            self.driver = webdriver.Chrome(options=options)
            stealth(self.driver,
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win64",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True)

            bootstrap_url = self._get_cookie_bootstrap_url(url)
            self.driver.get(bootstrap_url)
            for key, value in current_cookies.items():
                self.driver.add_cookie({"name": key, "value": value, "domain": ".lianjia.com", "path": "/"})
            
            self.logger.info(f"✓ 浏览器已启动，正在访问: {url}")
            self.driver.get(url)
            
            # 等待用户操作
            self.logger.info("")
            self.logger.info("=" * 60)
            self.logger.warning("⏳ 请在浏览器中完成验证！")
            self.logger.info("=" * 60)
            self.logger.info("步骤：")
            self.logger.info("  1. 完成滑块验证/输入验证码")
            self.logger.info("  2. 确保页面正常加载（能看到房源列表）")
            self.logger.info("  3. 验证完成后，回到此窗口")
            
            if wait_seconds > 0:
                self.logger.info(f"  4. 程序会自动检测页面是否加载完成，最多等待 {wait_seconds} 秒")
            else:
                self.logger.info("  4. 程序会持续检测，直到页面加载完成")
            self.logger.info("=" * 60)

            start_time = time.time()
            last_status_log = 0
            while True:
                page_state = self._inspect_page_state()
                if (
                    page_state['ready_state'] in ('interactive', 'complete') and
                    page_state['has_page_content'] and
                    not page_state['is_blocked']
                ):
                    self.logger.info("✓ 检测到页面已完成加载")
                    break

                now = time.time()
                if now - last_status_log >= 5:
                    blocked_reason = ", ".join(page_state['blocked_hits']) if page_state['blocked_hits'] else "none"
                    self.logger.info(
                        "⏳ 等待验证码通过后的页面加载完成... "
                        f"当前页面: {page_state['current_url']} | "
                        f"readyState={page_state['ready_state']} | "
                        f"content={page_state['has_page_content']} | "
                        f"blocked={page_state['is_blocked']} | "
                        f"iframe={page_state['has_verification_iframe']} | "
                        f"body_len={page_state['body_length']} | "
                        f"hits={blocked_reason}"
                    )
                    last_status_log = now

                if wait_seconds > 0 and (now - start_time) >= wait_seconds:
                    self.logger.warning("⚠️ 等待页面加载超时，将按当前页面状态继续")
                    break

                time.sleep(1)
            
            # 提取Cookie
            cookies = self.driver.get_cookies()
            cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
            page_source = self.driver.page_source
            current_url = self.driver.current_url
            page_title = self.driver.title
            
            self.logger.info(f"✓ 成功提取 {len(cookie_dict)} 个Cookie")
            
            # 显示关键Cookie
            key_cookies = ['lianjia_uuid', 'lianjia_ssid', 'select_city', 'lianjia_token']
            found_keys = [k for k in key_cookies if k in cookie_dict]
            if found_keys:
                self.logger.info(f"  关键Cookie: {', '.join(found_keys)}")
            
            self.logger.info(f"✓ 当前页面: {page_title} ({current_url})")
            
            return {
                'cookies': cookie_dict,
                'page_source': page_source,
                'current_url': current_url,
                'title': page_title,
            }
            
        except Exception as e:
            self.logger.error(f"浏览器操作失败: {e}")
            raise
        finally:
            if self.driver:
                self.logger.info("正在关闭浏览器...")
                self.driver.quit()
                self.logger.info("✓ 浏览器已关闭")


def update_cookies_with_selenium(url='https://sh.lianjia.com/ershoufang/', 
                                 current_cookies=None,
                                 config_path='config/cookies.json',
                                 wait_seconds=60,
                                 return_page_data=False):
    """
    使用Selenium更新Cookie的便捷函数
    
    Args:
        url: 要访问的URL
        config_path: Cookie保存路径
        wait_seconds: 等待用户验证的秒数（0=无限等待）
        return_page_data: 是否返回浏览器当前页面信息
    """
    logger = get_logger()
    
    helper = SeleniumCookieHelper(browser='edge')
    
    try:
        # 打开浏览器，等待用户验证
        result = helper.open_for_manual_verification(url, current_cookies or {}, wait_seconds)
        
        if not result or not result.get('cookies'):
            logger.error("未获取到Cookie")
            return None if return_page_data else False
        
        cookies = result['cookies']
        
        # 保存Cookie
        import os
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        config_data = {
            'cookies': cookies,
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'source': 'selenium_manual'
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
        
        logger.info(f"✓ Cookie已保存到: {config_path}")
        
        # 使Cookie管理器的缓存失效
        from cookie_manager import get_cookie_manager
        cookie_manager = get_cookie_manager(config_path)
        cookie_manager.invalidate_cache()
        
        logger.info("✓ Cookie缓存已刷新")
        
        if return_page_data:
            result['success'] = True
            return result
        
        return True
        
    except Exception as e:
        logger.error(f"Cookie更新失败: {e}")
        return None if return_page_data else False
