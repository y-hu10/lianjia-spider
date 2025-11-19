#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Cookie管理器 - 安全管理认证信息
"""

import os
import json
from typing import Dict, Optional
from logger import get_logger


class CookieManager:
    """Cookie管理器 - 从环境变量或配置文件加载Cookie"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化Cookie管理器
        
        Args:
            config_path: Cookie配置文件路径（可选）
        """
        self.logger = get_logger()
        self.config_path = config_path
        self._cookies = None
    
    def get_cookies(self) -> Dict[str, str]:
        """
        获取Cookie
        
        优先级：
        1. 环境变量
        2. 配置文件（.gitignore）
        3. 空Cookie（降级）
        
        Returns:
            Cookie字典
        """
        if self._cookies is not None:
            return self._cookies
        
        # 1. 尝试从环境变量读取
        cookies_from_env = self._load_from_env()
        if cookies_from_env:
            self.logger.info("✓ Cookie从环境变量加载")
            self._cookies = cookies_from_env
            return self._cookies
        
        # 2. 尝试从配置文件读取
        if self.config_path:
            cookies_from_file = self._load_from_file()
            if cookies_from_file:
                self.logger.info("✓ Cookie从配置文件加载")
                self._cookies = cookies_from_file
                return self._cookies
        
        # 3. 降级：使用空Cookie（可能会被限制访问）
        self.logger.warning("⚠️ 未找到Cookie配置，使用空Cookie（可能受限）")
        self._cookies = {}
        return self._cookies
    
    def _load_from_env(self) -> Optional[Dict[str, str]]:
        """
        从环境变量加载Cookie
        
        环境变量示例：
        export LIANJIA_COOKIE='{"lianjia_uuid":"xxx","lianjia_token":"yyy",...}'
        
        或者分别设置：
        export LIANJIA_UUID="xxx"
        export LIANJIA_TOKEN="yyy"
        ...
        """
        # 方式1：从单个JSON环境变量加载
        cookie_json = os.getenv('LIANJIA_COOKIE')
        if cookie_json:
            try:
                return json.loads(cookie_json)
            except json.JSONDecodeError as e:
                self.logger.error(f"环境变量LIANJIA_COOKIE格式错误: {e}")
        
        # 方式2：从多个独立环境变量加载
        cookie_keys = [
            'LIANJIA_UUID',
            'LIANJIA_SSID',
            'LIANJIA_TOKEN',
            'LIANJIA_TOKEN_SECURE',
            'SECURITY_TICKET',
            'LOGIN_UCID',
        ]
        
        cookies = {}
        for key in cookie_keys:
            value = os.getenv(key)
            if value:
                # 转换为cookie名称（小写，下划线）
                cookie_name = key.lower()
                cookies[cookie_name] = value
        
        return cookies if cookies else None
    
    def _load_from_file(self) -> Optional[Dict[str, str]]:
        """
        从配置文件加载Cookie
        
        配置文件格式（JSON）：
        {
            "lianjia_uuid": "xxx",
            "lianjia_token": "yyy",
            ...
        }
        """
        try:
            if not os.path.exists(self.config_path):
                return None
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('cookies', {})
        
        except Exception as e:
            self.logger.error(f"加载Cookie配置文件失败: {e}")
            return None
    
    def update_cookies(self, new_cookies: Dict[str, str]):
        """
        更新Cookie（用于刷新过期的Cookie）
        
        Args:
            new_cookies: 新的Cookie字典
        """
        self._cookies = new_cookies
        self.logger.info("Cookie已更新")
        
        # 如果有配置文件路径，保存到文件
        if self.config_path:
            try:
                with open(self.config_path, 'r+', encoding='utf-8') as f:
                    config = json.load(f)
                    config['cookies'] = new_cookies
                    f.seek(0)
                    json.dump(config, f, indent=4, ensure_ascii=False)
                    f.truncate()
                self.logger.info(f"Cookie已保存到 {self.config_path}")
            except Exception as e:
                self.logger.error(f"保存Cookie失败: {e}")
    
    def is_valid(self) -> bool:
        """
        检查Cookie是否有效
        
        Returns:
            True表示有效
        """
        cookies = self.get_cookies()
        
        # 检查必要的Cookie字段
        required_fields = ['lianjia_uuid', 'select_city']
        for field in required_fields:
            if field not in cookies or not cookies[field]:
                self.logger.warning(f"Cookie缺少必要字段: {field}")
                return False
        
        return True


# 全局实例
_cookie_manager = None


def get_cookie_manager(config_path: Optional[str] = None) -> CookieManager:
    """
    获取全局Cookie管理器实例
    
    Args:
        config_path: Cookie配置文件路径
        
    Returns:
        CookieManager实例
    """
    global _cookie_manager
    if _cookie_manager is None:
        _cookie_manager = CookieManager(config_path)
    return _cookie_manager


