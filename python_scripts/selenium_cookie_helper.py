#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
集成Selenium自动Cookie更新的爬虫
在检测到验证码时自动打开浏览器，等待用户验证后自动提取Cookie
"""

import json
import time
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
    
    def open_for_manual_verification(self, url, current_cookies, wait_seconds=60):
        """
        打开浏览器供用户手动验证，然后自动提取Cookie
        
        Args:
            url: 要访问的URL
            wait_seconds: 等待用户验证的秒数（0=无限等待）
            
        Returns:
            Cookie字典
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
            self.driver.get(url)
            for key, value in current_cookies.items():
                self.driver.add_cookie({"name":key, "value": value, "domain": ".lianjia.com", "path": "/"}) 
            
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
                self.logger.info(f"  4. 将在 {wait_seconds} 秒后自动继续")
                self.logger.info("")
                
                # 倒计时
                for remaining in range(wait_seconds, 0, -10):
                    if remaining <= wait_seconds:
                        self.logger.info(f"⏱  还有 {remaining} 秒... （可随时按Ctrl+C跳过等待）")
                    try:
                        time.sleep(min(10, remaining))
                    except KeyboardInterrupt:
                        self.logger.info("⏭  已跳过等待")
                        break
            else:
                self.logger.info("  4. 完成后按 Enter 继续")
                self.logger.info("=" * 60)
                input("\n按 Enter 继续...")
            
            # 提取Cookie
            cookies = self.driver.get_cookies()
            cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
            
            self.logger.info(f"✓ 成功提取 {len(cookie_dict)} 个Cookie")
            
            # 显示关键Cookie
            key_cookies = ['lianjia_uuid', 'lianjia_ssid', 'select_city', 'lianjia_token']
            found_keys = [k for k in key_cookies if k in cookie_dict]
            if found_keys:
                self.logger.info(f"  关键Cookie: {', '.join(found_keys)}")
            
            return cookie_dict
            
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
                                 wait_seconds=60):
    """
    使用Selenium更新Cookie的便捷函数
    
    Args:
        url: 要访问的URL
        config_path: Cookie保存路径
        wait_seconds: 等待用户验证的秒数（0=无限等待）
    """
    logger = get_logger()
    
    helper = SeleniumCookieHelper(browser='edge')
    
    try:
        # 打开浏览器，等待用户验证
        cookies = helper.open_for_manual_verification(url, current_cookies, wait_seconds)
        
        if not cookies:
            logger.error("未获取到Cookie")
            return False
        
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
        
        return True
        
    except Exception as e:
        logger.error(f"Cookie更新失败: {e}")
        return False