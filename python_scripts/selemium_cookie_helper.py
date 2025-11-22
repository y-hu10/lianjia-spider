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
from logger import get_logger


class SeleniumCookieHelper:
    """Selenium Cookie辅助工具"""
    
    def __init__(self, browser='edge'):
        self.browser = browser
        self.logger = get_logger()
        self.driver = None
    
    def open_for_manual_verification(self, url, wait_seconds=60):
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
            options = EdgeOptions()
            # 不使用无头模式，让用户可以看到浏览器
            options.add_argument('--start-maximized')
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            
            self.driver = webdriver.Edge(options=options)
            
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
    
    def auto_extract_cookies(self, url, timeout=10):
        """
        自动提取Cookie（不等待用户操作，用于页面没有验证码的情况）
        
        Args:
            url: 要访问的URL
            timeout: 页面加载超时时间
            
        Returns:
            Cookie字典
        """
        try:
            options = EdgeOptions()
            options.add_argument('--headless')  # 无头模式
            options.add_argument('--disable-gpu')
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            
            self.driver = webdriver.Edge(options=options)
            self.driver.set_page_load_timeout(timeout)
            
            self.driver.get(url)
            time.sleep(3)  # 等待Cookie设置
            
            cookies = self.driver.get_cookies()
            cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
            
            return cookie_dict
            
        finally:
            if self.driver:
                self.driver.quit()


def update_cookies_with_selenium(url='https://sh.lianjia.com/ershoufang/', 
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
        cookies = helper.open_for_manual_verification(url, wait_seconds)
        
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


# ============ 修改 spider.py 中的 _handle_blocked_response 方法 ============

"""
将以下代码添加到 spider.py 的 AntiBlockSpider 类中：

def _handle_blocked_response(self, html: str, url: str, attempt: int) -> bool:
    '''处理被封禁的响应'''
    is_blocked, reason, analysis = self._check_blocked(html, url)
    
    if not is_blocked:
        return False
    
    self.logger.error(f"  [封禁检测] {reason}")
    
    block_type = analysis.get('block_type', 'unknown')
    
    if block_type == 'captcha':
        self.logger.error("=" * 60)
        self.logger.error("🚫 检测到验证码，启动自动更新流程...")
        self.logger.error("=" * 60)
        
        # ⭐ 新增：使用Selenium自动更新Cookie
        try:
            from selenium_cookie_helper import update_cookies_with_selenium
            
            success = update_cookies_with_selenium(
                url=url,
                config_path=self.cookie_manager.config_path,
                wait_seconds=60  # 等待60秒供用户验证
            )
            
            if success:
                self.logger.info("✓ Cookie已自动更新！")
                # 强制重新加载Cookie
                self.cookie_manager.invalidate_cache()
                self.cookie_fail_count = 0
                return True  # 继续重试
            else:
                self.logger.error("✗ Cookie更新失败")
                
        except ImportError:
            self.logger.error("未找到Selenium模块，请安装: pip install selenium")
        except Exception as e:
            self.logger.error(f"自动更新Cookie时出错: {e}")
        
        # 如果自动更新失败，回退到手动模式
        self.logger.error("请手动更新Cookie")
        self.cookie_fail_count += 1
        
        if self.cookie_fail_count >= self.max_cookie_fails:
            raise Exception("Cookie失效次数过多，终止运行")
        
        time.sleep(60)
        
    elif block_type == 'rate_limit':
        penalty = random.uniform(30, 60)
        self.logger.warning(f"[限流] 等待 {penalty:.0f}秒...")
        time.sleep(penalty)
        
    elif block_type == 'ip_ban':
        self.logger.error("🚫 IP可能被封禁")
        penalty = random.uniform(60, 120)
        time.sleep(penalty)
    
    else:
        penalty = random.uniform(30, 60)
        self.logger.warning(f"[未知封禁] 等待 {penalty:.0f}秒...")
        time.sleep(penalty)
    
    return True
"""

# ============ 完整的使用示例 ============

if __name__ == '__main__':
    """
    独立运行此脚本来更新Cookie
    """
    from logger import setup_logger
    import logging
    
    setup_logger(log_level=logging.INFO)
    
    print("\n" + "=" * 60)
    print("🍪 链家Cookie自动更新工具（集成版）")
    print("=" * 60)
    print("\n提示：")
    print("  - 浏览器将自动打开链家网站")
    print("  - 如出现验证码，请手动完成验证")
    print("  - 验证完成后，Cookie将自动保存")
    print("  - 60秒后自动继续（或按Enter提前继续）")
    print("\n" + "=" * 60 + "\n")
    
    success = update_cookies_with_selenium(
        url='https://sh.lianjia.com/ershoufang/',
        config_path='config/cookies.json',
        wait_seconds=60
    )
    
    if success:
        print("\n" + "=" * 60)
        print("✅ Cookie更新成功！现在可以运行爬虫了")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ Cookie更新失败")
        print("=" * 60)
