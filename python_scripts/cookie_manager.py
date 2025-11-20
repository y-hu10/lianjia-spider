#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修复后的 Cookie 管理器 - 解决更新失效问题
"""

import os
import json
import time
from typing import Dict, Optional
from logger import get_logger


class CookieManager:
    """Cookie管理器 - 支持动态刷新"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化Cookie管理器
        
        Args:
            config_path: Cookie配置文件路径（可选）
        """
        self.logger = get_logger()
        self.config_path = config_path
        self._cookies = None
        self._last_update_time = 0
        self._cache_ttl = 300  # Cookie缓存5分钟后强制重新加载
    
    def get_cookies(self, force_reload=False) -> Dict[str, str]:
        """
        获取Cookie（支持强制重新加载）
        
        Args:
            force_reload: 是否强制从源重新加载
        
        优先级：
        1. 环境变量
        2. 配置文件（.gitignore）
        3. 空Cookie（降级）
        
        Returns:
            Cookie字典
        """
        current_time = time.time()
        
        # 检查是否需要刷新缓存
        cache_expired = (current_time - self._last_update_time) > self._cache_ttl
        
        if not force_reload and self._cookies is not None and not cache_expired:
            return self._cookies.copy()  # 返回副本，避免外部修改
        
        if cache_expired:
            self.logger.debug("Cookie缓存过期，重新加载")
        
        # 1. 尝试从环境变量读取
        cookies_from_env = self._load_from_env()
        if cookies_from_env:
            self.logger.info("✓ Cookie从环境变量加载")
            self._cookies = cookies_from_env
            self._last_update_time = current_time
            return self._cookies.copy()
        
        # 2. 尝试从配置文件读取
        if self.config_path:
            cookies_from_file = self._load_from_file()
            if cookies_from_file:
                self.logger.info("✓ Cookie从配置文件加载")
                self._cookies = cookies_from_file
                self._last_update_time = current_time
                return self._cookies.copy()
        
        # 3. 降级：使用空Cookie（可能会被限制访问）
        self.logger.warning("⚠️ 未找到Cookie配置，使用空Cookie（可能受限）")
        self._cookies = {}
        self._last_update_time = current_time
        return self._cookies.copy()
    
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
            'SELECT_CITY',  # 添加城市选择cookie
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
            "cookies": {
                "lianjia_uuid": "xxx",
                "lianjia_token": "yyy",
                ...
            },
            "last_update": "2024-01-01 12:00:00"
        }
        """
        try:
            if not os.path.exists(self.config_path):
                self.logger.debug(f"Cookie配置文件不存在: {self.config_path}")
                return None
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                cookies = config.get('cookies', {})
                
                # 记录文件更新时间
                last_update = config.get('last_update', 'unknown')
                self.logger.debug(f"Cookie文件最后更新: {last_update}")
                
                return cookies
        
        except Exception as e:
            self.logger.error(f"加载Cookie配置文件失败: {e}")
            return None
    
    def update_cookies(self, new_cookies: Dict[str, str], source="manual"):
        """
        更新Cookie（立即清除缓存并保存）
        
        Args:
            new_cookies: 新的Cookie字典
            source: 更新来源标识
        """
        # 立即更新内存中的cookie
        self._cookies = new_cookies.copy()
        self._last_update_time = time.time()
        
        self.logger.info(f"Cookie已更新 (来源: {source})")
        
        # 如果有配置文件路径，保存到文件
        if self.config_path:
            try:
                # 准备保存的数据
                save_data = {
                    'cookies': new_cookies,
                    'last_update': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'source': source
                }
                
                # 确保目录存在
                os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                
                # 保存到文件
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(save_data, f, indent=4, ensure_ascii=False)
                
                self.logger.info(f"✓ Cookie已保存到 {self.config_path}")
                
            except Exception as e:
                self.logger.error(f"✗ 保存Cookie失败: {e}", exc_info=True)
    
    def invalidate_cache(self):
        """
        使缓存失效，强制下次重新加载
        """
        self._cookies = None
        self._last_update_time = 0
        self.logger.debug("Cookie缓存已清除")
    
    def is_valid(self) -> bool:
        """
        检查Cookie是否有效
        
        Returns:
            True表示有效
        """
        cookies = self.get_cookies()
        
        if not cookies:
            self.logger.warning("Cookie为空")
            return False
        
        # 检查必要的Cookie字段（根据链家实际需求调整）
        required_fields = [
            'lianjia_uuid',
            'select_city',
        ]
        
        # 可选但建议有的字段
        recommended_fields = [
            'lianjia_ssid',
            'lianjia_token',
        ]
        
        missing_required = []
        missing_recommended = []
        
        for field in required_fields:
            if field not in cookies or not cookies[field]:
                missing_required.append(field)
        
        for field in recommended_fields:
            if field not in cookies or not cookies[field]:
                missing_recommended.append(field)
        
        if missing_required:
            self.logger.warning(f"Cookie缺少必要字段: {missing_required}")
            return False
        
        if missing_recommended:
            self.logger.info(f"Cookie缺少推荐字段: {missing_recommended} (可能影响访问)")
        
        return True
    
    def get_cookie_summary(self) -> str:
        """
        获取Cookie摘要信息（用于调试）
        """
        cookies = self.get_cookies()
        
        if not cookies:
            return "无Cookie"
        
        # 显示部分信息，隐藏敏感数据
        summary = []
        for key, value in cookies.items():
            if len(value) > 10:
                masked_value = value[:4] + "..." + value[-4:]
            else:
                masked_value = "***"
            summary.append(f"{key}={masked_value}")
        
        return "; ".join(summary)


# 全局单例实例
_cookie_manager = None


def get_cookie_manager(config_path: Optional[str] = None) -> CookieManager:
    """
    获取全局Cookie管理器实例（真正的单例）
    
    Args:
        config_path: Cookie配置文件路径
        
    Returns:
        CookieManager实例
    """
    global _cookie_manager
    
    # 如果已有实例且config_path相同，直接返回
    if _cookie_manager is not None:
        if config_path is None or _cookie_manager.config_path == config_path:
            return _cookie_manager
        else:
            # config_path改变了，重新创建
            _cookie_manager = None
    
    # 创建新实例
    _cookie_manager = CookieManager(config_path)
    return _cookie_manager


def reset_cookie_manager():
    """
    重置全局Cookie管理器（用于测试或强制刷新）
    """
    global _cookie_manager
    _cookie_manager = None
