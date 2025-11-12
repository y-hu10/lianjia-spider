#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import json
import time
from bs4 import BeautifulSoup
from random import randrange
from typing import List, Dict, Set
from logger import get_logger

class Spider:
    def __init__(self, host, locale, t='l2', min_price=0, max_price=0):
        self.base_url = host
        self.ershoufang_url = self.base_url + '/ershoufang'
        self.locale = locale
        self.price = 'bp' + str(min_price) + 'ep' + str(max_price) if max_price>0 else ""
        self.type = t
        self.logger = get_logger()

    def requestLocale(self):
        """原有的请求方法，增加错误处理"""
        page = 1
        total_page = 1
        data = []
        
        while True:
            url = self.ershoufang_url + '/' + self.locale + '/pg' + str(page) + self.type + self.price
            self.logger.info(url)
            
            try:
                html = self.__requestsGet(url)
                soup = BeautifulSoup(html, 'lxml')

                if total_page == 1 and soup.find('div', {'class': 'page-box fr'}):
                    page_data = soup.find('div', {'class': 'page-box fr'}).div
                    if page_data and 'page-data' in page_data.attrs:
                        total_page = json.loads(page_data.attrs['page-data'])['totalPage']
            
                page_data = self.__extractInformation(soup)
                data += page_data
                
            except Exception as e:
                self.logger.info(f"      页面 {page} 解析失败: {e}")
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
        stable_count = 0
        previous_ids = set()
        
        for attempt in range(1, max_attempts + 1):
            self.logger.info(f"  第 {attempt} 次请求...")
            
            try:
                current_data = self.requestLocale()
                current_ids = {house['house_id'] for house in current_data}
                
                self.logger.info(f"    获取到 {len(current_data)} 套房源")
                
                # 合并到总结果中（使用字典去重）
                for house in current_data:
                    # 使用 house_id 作为唯一标识
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
                
                # 避免请求过快
                if attempt < max_attempts:
                    time.sleep(randrange(5))
                    
            except Exception as e:
                self.logger.info(f"    ✗ 请求失败: {e}")
                if attempt < max_attempts:
                    time.sleep(3)
                continue
        
        if attempt == max_attempts + 1:
            self.logger.info(f"  ⚠ 警告: 未达到稳定状态，返回并集结果 ({len(all_results)} 套)")
        
        return all_results

    def __requestsGet(self, url, max_retries=3):
        """增加重试机制的请求方法"""
        cookie = {
            "lianjia_uuid": "bcc9dc71-1228-4d3a-b67a-85a8a4603980",
            "lfrc_": "ae2ec8b8-6102-417e-a5a3-68edb0b380dd",
            "ftkrc_": "ceea1c93-9154-40f8-b674-939d7d91f68d",
            "select_city": "310000",
            "lianjia_ssid": "edbb8bb0-5225-4295-81ce-9046f50d5096",
            "login_ucid": "2000000016997051",
            "lianjia_token": "2.001091db006917ec57013cf2317370d714",
            "lianjia_token_secure": "2.001091db006917ec57013cf2317370d714",
            "security_ticket": "gHOtkas33otGC0hu4c3BR7n+Mn71dDuKZ5CUTp6cIc0UIK+T67XNAl+acFhaogepr9OJH+ISa4QOIW5HGseJ8knc1jMXCZytcH/ID+065RhtmVoigZriY129aVszvYSAeRZlv9yJ9jeGjRYEnn5nj+u4sY+fzR/cwTi5e4mOogs=",
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Accept-Charset": "UTF-8"
        }
        
        for attempt in range(max_retries):
            try:
                r = requests.get(url, headers=headers, cookies=cookie, timeout=10)
                r.raise_for_status()
                return r.text
            except requests.RequestException as e:
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)  # 指数退避

    def __extractInformation(self, soup):
        """增加错误处理的信息提取"""
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
            except (AttributeError, IndexError, ValueError, KeyError) as e:
                # 跳过解析失败的房源
                continue
        
        return data
