#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
集成Selenium自动Cookie更新的爬虫
在检测到验证码时自动打开浏览器，等待用户验证后自动提取Cookie
"""

import json
import time
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

    def _is_page_ready(self):
        """检测页面是否完成加载且已离开验证码页。"""
        page_source = self.driver.page_source
        current_url = self.driver.current_url
        ready_state = self.driver.execute_script("return document.readyState")

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
        is_blocked = any(marker in page_text or marker in url_text for marker in blocked_markers)
        has_listing = (
            'sellListContent' in page_source or
            'page-box fr' in page_source or
            'totalSellCount' in page_source
        )

        return ready_state == 'complete' and has_listing and not is_blocked
    
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
                if self._is_page_ready():
                    self.logger.info("✓ 检测到页面已完成加载")
                    break

                now = time.time()
                if now - last_status_log >= 5:
                    self.logger.info(f"⏳ 等待验证码通过后的页面加载完成... 当前页面: {self.driver.current_url}")
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
