#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
改进的验证页面检测机制
"""

import re
from typing import Dict, Tuple
from bs4 import BeautifulSoup
from logger import get_logger


class BlockDetector:
    """封禁/验证页面检测器"""
    
    def __init__(self):
        self.logger = get_logger()
        
        # 文本关键词（简单但有效）
        self.text_indicators = [
            # 中文关键词
            #'访问验证', '安全验证', '请完成验证', '滑动验证',
            #'频繁访问', '异常访问', '请稍后再试',
            #'您的访问过于频繁', '请输入验证码',
            #'安全检测', '行为验证', '人机验证',
            #'访问被拒绝', '访问受限', '暂时无法访问',
            "人机验证",
            "captcha.lianjia.com", 
            # 英文关键词
            #'captcha', 'verification', 'security check',
            #'access denied', 'forbidden', 'too many requests',
            #'anti-bot', 'robot check', 'prove you are human',
            #'unusual activity', 'suspicious activity',
            
            # HTTP状态相关
            #'403', '429', '503',
        ]
        
        # HTML元素特征
        self.html_indicators = {
            # 验证码相关class/id
            'classes': [
                'captcha', 'verification',
                'security-check', 'anti-bot', 'robot-check',
                'slider-verify', 'geetest', 'turnstile',
                'recaptcha', 'hcaptcha',
            ],
            # 验证码相关标签
            'tags': [
                'iframe',  # 验证码通常在iframe中
            ],
            # 验证码相关URL片段
            'urls': [
                'captcha', 'security',
                'geetest', 'recaptcha', 'hcaptcha',
                'challenge', 'anti-bot',
            ]
        }
        
        # 页面结构特征
        self.structure_indicators = {
            'missing_elements': [
                # 正常页面应该有的元素
                'sellListContent',  # 链家房源列表
                'page-box',  # 分页
            ],
            'abnormal_title': [
                '验证', '安全', 'verify', 'captcha',
                '403', '404', '500', '503',
            ]
        }
    
    def check_blocked(self, html: str, url: str = "") -> Tuple[bool, str]:
        """
        综合检测是否被封禁/需要验证
        
        Args:
            html: HTML内容
            url: 请求URL（可选）
            
        Returns:
            (是否被封禁, 检测原因)
        """
        reasons = []
        
        # 1. 检查文本关键词
        text_result, text_reason = self._check_text_indicators(html)
        if text_result:
            reasons.append(text_reason)
        
        # 2. 检查HTML元素特征
        html_result, html_reason = self._check_html_indicators(html)
        if html_result:
            reasons.append(html_reason)
        
        # 3. 检查页面结构
        structure_result, structure_reason = self._check_structure(html)
        if structure_result:
            reasons.append(structure_reason)
        
        # 4. 检查响应长度（验证页面通常很短）
        length_result, length_reason = self._check_response_length(html)
        if length_result:
            reasons.append(length_reason)
        
        # 5. 检查URL重定向特征
        if url:
            url_result, url_reason = self._check_url_pattern(url)
            if url_result:
                reasons.append(url_reason)
        
        is_blocked = len(reasons) > 0
        reason = " | ".join(reasons) if reasons else "正常"
        
        if is_blocked:
            self.logger.warning(f"🚫 检测到封禁/验证: {reason}")
        
        return is_blocked, reason
    
    def _check_text_indicators(self, html: str) -> Tuple[bool, str]:
        """检查文本关键词"""
        html_lower = html.lower()
        
        for indicator in self.text_indicators:
            if indicator.lower() in html_lower:
                return True, f"文本关键词: '{indicator}'"
        
        return False, ""
    
    def _check_html_indicators(self, html: str) -> Tuple[bool, str]:
        """检查HTML元素特征"""
        try:
            soup = BeautifulSoup(html, 'lxml')
            
            # 检查class属性
            for cls in self.html_indicators['classes']:
                if soup.find(class_=re.compile(cls, re.I)):
                    return True, f"HTML类名: '{cls}'"
                if soup.find(id=re.compile(cls, re.I)):
                    return True, f"HTML ID: '{cls}'"
            
            # 检查iframe（验证码常用）
            iframes = soup.find_all('iframe')
            for iframe in iframes:
                src = iframe.get('src', '')
                for url_pattern in self.html_indicators['urls']:
                    if url_pattern in src.lower():
                        return True, f"验证iframe: '{url_pattern}' in '{src}'"
            
            # 检查script标签中的验证码初始化代码
            scripts = soup.find_all('script')
            for script in scripts:
                script_text = script.string or ''
                for url_pattern in self.html_indicators['urls']:
                    if url_pattern in script_text.lower():
                        return True, f"验证脚本: '{url_pattern}'"
            
        except Exception as e:
            self.logger.debug(f"HTML元素检查失败: {e}")
        
        return False, ""
    
    def _check_structure(self, html: str) -> Tuple[bool, str]:
        """检查页面结构"""
        try:
            soup = BeautifulSoup(html, 'lxml')
            page_text = soup.get_text(" ", strip=True)
            title = soup.find('title')
            title_text = title.string.strip() if title and title.string else ""
            
            has_known_listing_marker = (
                soup.find(class_='sellListContent') is not None or
                soup.find(class_='page-box') is not None or
                soup.find(class_='content__list') is not None or
                soup.find(attrs={'data-lj_action_housedel_id': True}) is not None
            )
            has_meaningful_content = (
                len(page_text) >= 200 and
                any(keyword in page_text for keyword in ('二手房', '房源', '总价', '单价', '带看', '关注', '链家'))
            )
            
            # 检查关键元素是否缺失
            missing_count = 0
            for element_class in self.structure_indicators['missing_elements']:
                if not soup.find(class_=element_class):
                    missing_count += 1
            
            # 如果所有旧版关键元素都缺失，同时又看不到有效内容，才判定为异常页面。
            if (
                missing_count == len(self.structure_indicators['missing_elements']) and
                not has_known_listing_marker and
                not has_meaningful_content
            ):
                return True, f"缺失关键页面元素"
            
            # 检查标题
            if title_text:
                title_text_lower = title_text.lower()
                for abnormal in self.structure_indicators['abnormal_title']:
                    if abnormal.lower() in title_text_lower and not has_meaningful_content:
                        return True, f"异常页面标题: '{title_text}'"
            
        except Exception as e:
            self.logger.debug(f"结构检查失败: {e}")
        
        return False, ""
    
    def _check_response_length(self, html: str) -> Tuple[bool, str]:
        """检查响应长度"""
        length = len(html)
        
        # 链家正常房源列表页面通常 > 50KB
        # 验证页面通常 < 10KB
        if length < 10000:  # 10KB
            return True, f"响应过短: {length} bytes"
        
        return False, ""
    
    def _check_url_pattern(self, url: str) -> Tuple[bool, str]:
        """检查URL模式"""
        url_lower = url.lower()
        
        # 检查是否被重定向到验证页面
        suspicious_paths = [
            '/captcha', '/verify', '/security',
            '/blocked', '/forbidden', '/error',
        ]
        
        for path in suspicious_paths:
            if path in url_lower:
                return True, f"可疑URL: '{path}' in '{url}'"
        
        return False, ""
    
    def analyze_block_page(self, html: str) -> Dict:
        """
        深度分析封禁页面，提取详细信息
        
        Returns:
            分析结果字典
        """
        analysis = {
            'is_blocked': False,
            'block_type': 'unknown',  # captcha, rate_limit, ip_ban, etc.
            'captcha_type': None,  # geetest, recaptcha, hcaptcha, slider, etc.
            'error_message': None,
            'retry_after': None,  # 如果有Retry-After信息
            'suggestions': []
        }
        
        try:
            soup = BeautifulSoup(html, 'lxml')
            html_lower = html.lower()
            
            # 判断封禁类型
            if 'captcha' in html_lower or '验证码' in html:
                analysis['is_blocked'] = True
                analysis['block_type'] = 'captcha'
                
                # 识别验证码类型
                if 'geetest' in html_lower:
                    analysis['captcha_type'] = 'geetest'
                    analysis['suggestions'].append('检测到极验验证码，建议使用Selenium')
                elif 'recaptcha' in html_lower:
                    analysis['captcha_type'] = 'recaptcha'
                    analysis['suggestions'].append('检测到Google reCAPTCHA')
                elif 'hcaptcha' in html_lower:
                    analysis['captcha_type'] = 'hcaptcha'
                elif 'slider' in html_lower or '滑动' in html:
                    analysis['captcha_type'] = 'slider'
                    analysis['suggestions'].append('检测到滑块验证')
            
            elif '频繁' in html or '429' in html or 'too many' in html_lower:
                analysis['is_blocked'] = True
                analysis['block_type'] = 'rate_limit'
                analysis['suggestions'].extend([
                    '请求过于频繁',
                    '建议增加延迟至10-20秒',
                    '考虑使用代理IP'
                ])
            
            elif '403' in html or 'forbidden' in html_lower or '拒绝' in html:
                analysis['is_blocked'] = True
                analysis['block_type'] = 'ip_ban'
                analysis['suggestions'].extend([
                    'IP可能被封禁',
                    '建议更换IP地址',
                    '更新Cookie',
                    '检查User-Agent'
                ])
            
            # 提取错误消息
            error_divs = soup.find_all(['div', 'p'], class_=re.compile('error|message|tip', re.I))
            for div in error_divs:
                if div.get_text().strip():
                    analysis['error_message'] = div.get_text().strip()
                    break
            
            # 查找Retry-After信息
            retry_match = re.search(r'(\d+)\s*(秒|分钟|小时|second|minute|hour)', html)
            if retry_match:
                analysis['retry_after'] = retry_match.group(0)
                analysis['suggestions'].append(f'建议等待: {retry_match.group(0)}')
        
        except Exception as e:
            self.logger.error(f"分析封禁页面失败: {e}")
        
        return analysis
    
    def get_bypass_suggestions(self, block_type: str) -> list:
        """
        根据封禁类型给出绕过建议
        
        Args:
            block_type: 封禁类型
            
        Returns:
            建议列表
        """
        suggestions = {
            'captcha': [
                '1. 使用Selenium/Playwright模拟真实浏览器',
                '2. 集成打码平台（如2captcha）',
                '3. 降低爬取频率',
                '4. 更新Cookie',
            ],
            'rate_limit': [
                '1. 增加请求间隔（至少10秒）',
                '2. 使用代理IP轮换',
                '3. 分时段爬取（避开高峰）',
                '4. 减少并发数',
            ],
            'ip_ban': [
                '1. 更换IP地址（重启路由器或使用代理）',
                '2. 更新所有Cookie',
                '3. 等待24小时后重试',
                '4. 检查User-Agent是否正常',
            ],
            'unknown': [
                '1. 手动访问网站检查状态',
                '2. 查看浏览器开发者工具',
                '3. 更新Cookie',
                '4. 增加延迟',
            ]
        }
        
        return suggestions.get(block_type, suggestions['unknown'])


# 使用示例
"""
detector = BlockDetector()

# 基础检测
is_blocked, reason = detector.check_blocked(html, url)
if is_blocked:
    print(f"被封禁: {reason}")
    
    # 深度分析
    analysis = detector.analyze_block_page(html)
    print(f"封禁类型: {analysis['block_type']}")
    print(f"验证码类型: {analysis['captcha_type']}")
    print(f"错误信息: {analysis['error_message']}")
    
    # 获取建议
    suggestions = detector.get_bypass_suggestions(analysis['block_type'])
    for suggestion in suggestions:
        print(suggestion)
"""
