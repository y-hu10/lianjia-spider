#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
增强版爬虫 - 反反爬虫策略
"""

import requests
import json
import time
import random
from bs4 import BeautifulSoup
from typing import List, Dict, Set, Optional, Tuple
from logger import get_logger
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from cookie_manager import get_cookie_manager
from improved_block_detection import BlockDetector


class AntiBlockSpider:
    """反反爬虫增强版爬虫"""
    
    # 用户代理池
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]
    
    def __init__(self, host, locale, t='l2', min_price=0, max_price=0, 
                 use_proxy=False, min_delay=3, max_delay=8):
        """
        初始化爬虫
        
        Args:
            host: 主机地址
            locale: 区域
            t: 类型
            min_price: 最低价格
            max_price: 最高价格
            use_proxy: 是否使用代理
            min_delay: 最小延迟（秒）
            max_delay: 最大延迟（秒）
        """
        self.base_url = host
        self.ershoufang_url = self.base_url + '/ershoufang'
        self.locale = locale
        self.price = 'bp' + str(min_price) + 'ep' + str(max_price) if max_price > 0 else ""
        self.type = t
        self.logger = get_logger()
        
        # 反爬虫配置
        self.use_proxy = use_proxy
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.request_count = 0
        self.last_request_time = 0
        
        # 配置会话
        self.session = self._create_session()
    
    def _create_session(self):
        """创建带重试机制的会话"""
        session = requests.Session()
        
        # 配置重试策略
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,  # 指数退避: 2, 4, 8秒
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _get_random_user_agent(self):
        """随机获取User-Agent"""
        return random.choice(self.USER_AGENTS)
    
    def _get_headers(self):
        """生成随机请求头"""
        headers = {
            "User-Agent": self._get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
            "DNT": "1",  # Do Not Track
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }
        
        # 随机添加Referer（模拟从其他页面跳转）
        if self.request_count > 0 and random.random() > 0.3:
            headers["Referer"] = f"{self.base_url}/ershoufang/{self.locale}/"
        
        return headers
    
    def _get_cookies(self):
        """
        获取Cookie（应该从配置文件或环境变量读取）
        ⚠️ 注意：这里的Cookie需要定期更新！
        """
        cookie_mgr = get_cookie_manager('config/cookies.json')
        cookies = cookie_mgr.get_cookies()

        # 检查有效性
        if not cookie_mgr.is_valid():
            print("Cookie无效，请更新！")
        return cookies
    
    def _get_proxy(self):
        """
        获取代理（如果启用）
        需要配置代理池
        """
        if not self.use_proxy:
            return None
        
        # TODO: 实现代理池
        # 可以使用：
        # 1. 付费代理服务（如：阿布云、快代理）
        # 2. 自建代理池
        # 3. 免费代理（不推荐，质量差）
        
        proxies = {
            'http': 'http://proxy_ip:port',
            'https': 'http://proxy_ip:port',
        }
        return proxies
    
    def _smart_delay(self):
        """
        智能延迟策略
        - 基础随机延迟
        - 请求次数越多，延迟越长
        - 避免规律性请求
        """
        # 计算自上次请求的时间
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        # 基础延迟
        base_delay = random.uniform(self.min_delay, self.max_delay)
        
        # 每10次请求增加额外延迟
        if self.request_count % 10 == 0 and self.request_count > 0:
            extra_delay = random.uniform(5, 15)
            self.logger.info(f"  [反爬] 第{self.request_count}次请求，额外休息 {extra_delay:.1f}秒")
            base_delay += extra_delay
        
        # 每50次请求长时间休息
        if self.request_count % 50 == 0 and self.request_count > 0:
            long_delay = random.uniform(30, 60)
            self.logger.warning(f"  [反爬] 第{self.request_count}次请求，长时间休息 {long_delay:.1f}秒")
            base_delay += long_delay
        
        # 确保最小间隔
        if elapsed < base_delay:
            wait_time = base_delay - elapsed
            if wait_time > 1:
                self.logger.debug(f"  [延迟] 等待 {wait_time:.1f}秒")
            time.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    def _check_blocked(self, html: str, url: str = "") -> Tuple[bool, str, Dict]:
        """
        检查是否被封禁（使用改进的检测器）
        
        Returns:
            (是否被封禁, 原因, 详细分析)
        """
        
        detector = BlockDetector()
        is_blocked, reason = detector.check_blocked(html, url)
        
        analysis = {}
        if is_blocked:
            analysis = detector.analyze_block_page(html)
        
        return is_blocked, reason, analysis
    
    def _requestsGet(self, url, max_retries=3):
        """
        增强版GET请求
        
        Args:
            url: 目标URL
            max_retries: 最大重试次数
            
        Returns:
            HTML内容
        """
        self.request_count += 1
        
        for attempt in range(max_retries):
            try:
                # 智能延迟
                self._smart_delay()
                
                # 准备请求参数
                headers = self._get_headers()
                cookies = self._get_cookies()
                proxies = self._get_proxy()
                
                self.logger.debug(f"  [请求] 尝试 {attempt + 1}/{max_retries}")
                self.logger.debug(f"  [UA] {headers['User-Agent'][:50]}...")
                
                # 发送请求
                response = self.session.get(
                    url,
                    headers=headers,
                    cookies=cookies,
                    proxies=proxies,
                    timeout=15,
                    allow_redirects=True
                )
                
                response.raise_for_status()
                
                # 检查是否被封禁
                is_blocked, reason, analysis = self._check_blocked(response.text, url)
                
                if is_blocked:
                    self.logger.error(f"  [封禁] {reason}")
                    
                    # 打印详细分析
                    if analysis.get('block_type'):
                        self.logger.error(f"  [类型] {analysis['block_type']}")
                    if analysis.get('captcha_type'):
                        self.logger.error(f"  [验证码] {analysis['captcha_type']}")
                    if analysis.get('error_message'):
                        self.logger.error(f"  [消息] {analysis['error_message']}")
                    
                    # 打印建议
                    if analysis.get('suggestions'):
                        self.logger.warning(f"  [建议]:")
                        for sug in analysis['suggestions'][:3]:
                            self.logger.warning(f"    - {sug}")
                    
                    if attempt < max_retries - 1:
                        # 被封禁时增加更长延迟
                        penalty_delay = random.uniform(30, 60)
                        self.logger.warning(f"  [封禁] 等待 {penalty_delay:.1f}秒后重试...")
                        time.sleep(penalty_delay)
                        
                        # 如果是验证码，多等一会
                        if analysis.get('block_type') == 'captcha':
                            extra_delay = random.uniform(30, 60)
                            self.logger.warning(f"  [验证码] 额外等待 {extra_delay:.1f}秒...")
                            time.sleep(extra_delay)
                        
                        continue
                    else:
                        error_msg = f"多次尝试后仍被封禁: {analysis.get('block_type', 'unknown')}"
                        self.logger.error(f"  [终止] {error_msg}")
                        raise Exception(error_msg)
                
                # 成功返回
                return response.text
                
            except requests.HTTPError as e:
                if e.response.status_code == 429:
                    # 请求过于频繁
                    retry_after = int(e.response.headers.get('Retry-After', 60))
                    self.logger.warning(f"  [限流] 429错误，等待 {retry_after}秒")
                    time.sleep(retry_after)
                elif e.response.status_code == 403:
                    self.logger.error(f"  [403] 访问被拒绝，可能需要更新Cookie")
                    if attempt < max_retries - 1:
                        time.sleep(random.uniform(20, 40))
                    else:
                        raise
                else:
                    self.logger.error(f"  [HTTP错误] {e.response.status_code}")
                    if attempt == max_retries - 1:
                        raise
                        
            except requests.RequestException as e:
                self.logger.error(f"  [网络错误] {e}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)  # 指数退避
        
        raise Exception(f"请求失败，已重试{max_retries}次")
    
    def requestLocale(self):
        """请求指定区域的房源列表"""
        page = 1
        total_page = 1
        data = []
        
        while True:
            url = f"{self.ershoufang_url}/{self.locale}/pg{page}{self.type}{self.price}"
            self.logger.info(f"  页面 {page}/{total_page}: {url}")
            
            try:
                html = self._requestsGet(url)
                soup = BeautifulSoup(html, 'lxml')

                if total_page == 1 and soup.find('div', {'class': 'page-box fr'}):
                    page_data = soup.find('div', {'class': 'page-box fr'}).div
                    if page_data and 'page-data' in page_data.attrs:
                        total_page = json.loads(page_data.attrs['page-data'])['totalPage']
                        self.logger.info(f"  总页数: {total_page}")
            
                page_data = self._extractInformation(soup)
                data += page_data
                
                self.logger.debug(f"  本页提取: {len(page_data)} 套")
                
            except Exception as e:
                self.logger.error(f"  页面 {page} 解析失败: {e}")
                # 继续尝试下一页
            
            if page >= total_page:
                break
            page += 1
            
        return data

    def requestLocaleStable(self, max_attempts=3, stability_threshold=2):
        """
        多次请求直到结果稳定
        
        Args:
            max_attempts: 最大尝试次数
            stability_threshold: 连续多少次结果一致才认为稳定
            
        Returns:
            稳定的房源数据列表
        """
        self.logger.info(f"\n开始稳定抓取: {self.locale} (价格段: {self.price or '不限'})")
        
        all_results = []
        previous_ids = set()
        
        for attempt in range(1, max_attempts + 1):
            self.logger.info(f"  第 {attempt} 次请求...")
            
            try:
                current_data = self.requestLocale()
                current_ids = {house['house_id'] for house in current_data}
                
                self.logger.info(f"    获取到 {len(current_data)} 套房源")
                
                # 合并到总结果中
                for house in current_data:
                    if not any(h['house_id'] == house['house_id'] for h in all_results):
                        all_results.append(house)
                
                # 检查是否稳定
                if current_ids.issubset(previous_ids):
                    self.logger.info(f"    结果一致")
                    if attempt >= 2:
                        self.logger.info(f"  ✓ 结果已稳定，共 {len(all_results)} 套房源")
                        break
                else:
                    new_ids = current_ids - previous_ids
                    missing_ids = previous_ids - current_ids
                    if new_ids:
                        self.logger.info(f"    发现 {len(new_ids)} 个新房源ID")
                    if missing_ids:
                        self.logger.info(f"    缺少 {len(missing_ids)} 个房源ID")
                    previous_ids = previous_ids.union(current_ids)
                
                # 避免请求过快（在尝试间增加更长延迟）
                if attempt < max_attempts:
                    delay = random.uniform(10, 20)
                    self.logger.info(f"    等待 {delay:.1f}秒后进行下一次尝试...")
                    time.sleep(delay)
                    
            except Exception as e:
                self.logger.error(f"    ✗ 请求失败: {e}")
                if attempt < max_attempts:
                    delay = random.uniform(20, 40)
                    self.logger.warning(f"    失败后等待 {delay:.1f}秒重试...")
                    time.sleep(delay)
                continue
        
        if attempt == max_attempts:
            self.logger.warning(f"  ⚠ 警告: 未达到稳定状态，返回并集结果 ({len(all_results)} 套)")
        
        return all_results

    def _extractInformation(self, soup):
        """信息提取（与原版相同）"""
        house_list = soup.find('ul', {'class': 'sellListContent'})
        if not house_list:
            return []
        
        data = []
        for house in house_list:
            try:
                info = house.find("div", {'class': 'info'}, recursive=False)
                if not info:
                    continue
                
                house_title = info.find("div", {'class': 'title'}, recursive=False)
                if not house_title or not house_title.a:
                    continue
                
                house_id = int(house_title.a.attrs['href'].split('/')[-1][:-5])

                flood_div = info.find("div", {'class': 'flood'}, recursive=False)
                if not flood_div or not flood_div.div or not flood_div.div.a:
                    continue
                house_location = flood_div.div.a.string

                address_div = info.find("div", {'class': 'address'}, recursive=False)
                if not address_div:
                    continue
                address = address_div.text.split(' | ')
                
                if len(address) < 6:
                    continue
                
                house_type = address[0]
                house_size = address[1]
                house_towards = address[2]
                house_flood = address[4]
                
                if len(address) < 7:
                    house_year = ""
                    house_building = address[5]
                else:
                    house_year = address[5]
                    house_building = address[6]

                priceInfo = info.find("div", {'class': 'priceInfo'}, recursive=False)
                if not priceInfo:
                    continue
                
                total_price_div = priceInfo.find("div", {'class': 'totalPrice'}, recursive=False)
                unit_price_div = priceInfo.find("div", {'class': 'unitPrice'}, recursive=False)
                
                if not total_price_div or not total_price_div.span:
                    continue
                if not unit_price_div or not unit_price_div.span:
                    continue
                
                house_total_price = total_price_div.span.string + "万"
                house_unit_price = unit_price_div.span.string[2:-4]
                house_region = self.locale

                data.append({
                    'house_id': house_id,
                    'house_location': house_location,
                    'house_type': house_type,
                    'house_size': house_size,
                    'house_towards': house_towards,
                    'house_flood': house_flood,
                    'house_year': house_year,
                    'house_building': house_building,
                    'house_total_price': house_total_price,
                    'house_unit_price': house_unit_price,
                    'house_region': house_region
                })
            except (AttributeError, IndexError, ValueError, KeyError):
                continue
        
        return data


# 保持向后兼容
Spider = AntiBlockSpider
