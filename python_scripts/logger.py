#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
日志系统模块 - 统一管理所有日志输出
"""

import logging
import sys
import os
from datetime import datetime


class Logger:
    """单例日志管理器"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self.logger = None
        
    def setup(self, log_dir='logs', log_level=logging.INFO, console_output=True):
        """
        设置日志系统
        
        Args:
            log_dir: 日志文件目录
            log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            console_output: 是否同时输出到控制台
        """
        # 创建日志目录
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # 创建 logger
        self.logger = logging.getLogger('LianjiaSpider')
        self.logger.setLevel(log_level)
        
        # 清除已有的 handlers（避免重复）
        self.logger.handlers.clear()
        
        # 日志格式
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        simple_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # 文件处理器 - 详细日志（所有级别）
        log_filename = os.path.join(
            log_dir,
            f"lianjia_{datetime.now().strftime('%Y%m%d')}.log"
        )
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        self.logger.addHandler(file_handler)
        
        # 文件处理器 - 错误日志（只记录错误）
        error_filename = os.path.join(
            log_dir,
            f"lianjia_error_{datetime.now().strftime('%Y%m%d')}.log"
        )
        error_handler = logging.FileHandler(error_filename, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        self.logger.addHandler(error_handler)
        
        # 控制台处理器
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(log_level)
            console_handler.setFormatter(simple_formatter)
            self.logger.addHandler(console_handler)
        
        self.logger.info("=" * 60)
        self.logger.info("日志系统初始化完成")
        self.logger.info(f"日志文件: {log_filename}")
        self.logger.info(f"错误日志: {error_filename}")
        self.logger.info("=" * 60)
    
    def get_logger(self):
        """获取 logger 实例"""
        if self.logger is None:
            self.setup()
        return self.logger


# 全局函数，方便快速使用
def get_logger():
    """获取全局 logger 实例"""
    return Logger().get_logger()


def setup_logger(log_dir='logs', log_level=logging.INFO, console_output=True):
    """设置全局 logger"""
    Logger().setup(log_dir, log_level, console_output)
