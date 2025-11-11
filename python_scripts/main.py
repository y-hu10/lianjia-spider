#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
重构后的 main.py - 使用日志系统
"""

from spider import Spider
from database import Database
from logger import setup_logger, get_logger
import json
import sys
import logging
from datetime import datetime
from typing import List, Dict


def load_config(config_path='config/config.json'):
    """加载配置文件"""
    logger = get_logger()
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.loads(f.read())
        logger.info(f"配置文件加载成功: {config_path}")
        return config
    except Exception as e:
        logger.error(f"配置文件加载失败: {e}", exc_info=True)
        raise


def fetch_all_data(config):
    """
    根据配置批量抓取所有区域和价格段的数据
    
    Returns:
        所有房源数据的列表（已去重）
    """
    logger = get_logger()
    
    host = config['host']
    locales = config['locales']
    types = config.get('types', ['l2l3l4'])
    price_ranges = config['price_ranges']
    
    # 稳定性配置
    stability = config.get('stability', {})
    max_attempts = stability.get('max_attempts', 5)
    threshold = stability.get('threshold', 2)
    
    all_houses = {}  # 使用字典去重，key 为 house_id
    
    total_tasks = len(locales) * len(types) * len(price_ranges)
    current_task = 0
    
    logger.info("=" * 60)
    logger.info("开始批量抓取:")
    logger.info(f"  区域: {len(locales)} 个 - {locales}")
    logger.info(f"  类型: {len(types)} 个 - {types}")
    logger.info(f"  价格段: {len(price_ranges)} 个")
    logger.info(f"  总任务数: {total_tasks}")
    logger.info(f"  稳定性要求: 最多 {max_attempts} 次尝试, {threshold} 次一致")
    logger.info("=" * 60)
    
    for locale in locales:
        for house_type in types:
            for price_range in price_ranges:
                current_task += 1
                min_price = price_range.get('min', 0)
                max_price = price_range.get('max', 0)
                
                logger.info("")
                logger.info(f"[{current_task}/{total_tasks}] 任务:")
                logger.info(f"  区域: {locale}")
                logger.info(f"  价格: {min_price}-{max_price}万")
                
                try:
                    spy = Spider(host, locale, house_type, min_price, max_price)
                    
                    # 使用稳定抓取方法
                    houses = spy.requestLocaleStable(
                        max_attempts=max_attempts,
                        stability_threshold=threshold
                    )
                    
                    # 合并数据（去重）
                    new_houses = 0
                    for house in houses:
                        house_id = house['house_id']
                        if house_id not in all_houses:
                            all_houses[house_id] = house
                            new_houses += 1
                    
                    logger.info(f"  本次新增: {new_houses} 套")
                    logger.info(f"  当前总计: {len(all_houses)} 套房源")
                    
                except Exception as e:
                    logger.error(f"  ✗ 任务失败: {e}", exc_info=True)
                    continue
    
    logger.info("")
    logger.info("=" * 60)
    logger.info(f"抓取完成! 共获取 {len(all_houses)} 套唯一房源")
    logger.info("=" * 60)
    
    return list(all_houses.values())


def process_houses(data, db, config, date):
    """
    处理房源数据：新增、变动、减少
    
    Returns:
        统计信息字典
    """
    logger = get_logger()
    
    stats = {
        'new_count': 0,
        'new_list': [],
        'change_count': 0,
        'change_list': [],
        'delete_count': 0,
        'delete_list': []
    }
    
    logger.info("")
    logger.info(f"处理房源数据 (日期: {date})...")
    
    # 处理每套房源
    for idx, house in enumerate(data, 1):
        if idx % 100 == 0:
            logger.debug(f"  已处理 {idx}/{len(data)} 套房源...")
        
        try:
            old_data = list(db.selectHouse(house['house_id']))
            
            if len(old_data) == 0:
                # 新增房源
                stats['new_count'] += 1
                url = f"{config['host']}/ershoufang/{house['house_id']}.html"
                stats['new_list'].append(url)
                
                house['house_date_price'] = json.dumps({
                    date: [house['house_total_price'], house['house_unit_price']]
                })
                db.insertHouse(house)
                logger.debug(f"  新增房源: {house['house_id']} - {house['house_location']}")
                
            else:
                # 已存在的房源，检查价格变动
                old_date_price = json.loads(old_data[0][-1])
                
                if date not in old_date_price:
                    old_date_price[date] = [
                        house['house_total_price'],
                        house['house_unit_price']
                    ]
                    house['house_date_price'] = json.dumps(old_date_price)
                    db.updateHouse(house)
                    
                    # 检查是否有价格变动
                    sorted_dates = sorted(old_date_price.keys())
                    if len(sorted_dates) >= 2:
                        last_date = sorted_dates[-2]
                        if old_date_price[last_date] != old_date_price[date]:
                            stats['change_count'] += 1
                            url = f"{config['host']}/ershoufang/{house['house_id']}.html"
                            stats['change_list'].append(url)
                            
                            old_price = old_date_price[last_date]
                            new_price = old_date_price[date]
                            logger.info(f"  价格变动: {house['house_id']} - {old_price} → {new_price}")
        
        except Exception as e:
            logger.error(f"  处理房源 {house.get('house_id', 'unknown')} 失败: {e}", exc_info=True)
            continue
    
    # 处理已售出房源
    try:
        db_count = db.countHouse()
        if db_count > len(data):
            stats['delete_count'] = db_count - len(data)
            logger.info(f"  检测到 {stats['delete_count']} 套房源已售出")
            
            for item in list(db.findAllSellOutFromHouse(date)):
                stats['delete_list'].append(
                    f"{config['host']}/ershoufang/{item[0]}.html"
                )
                
                # 移动到 SELLOUT 表
                del_data = list(db.selectHouse(item[0]))[0]
                db.insertSellOut({
                    'house_id': del_data[0],
                    'house_location': del_data[1],
                    'house_type': del_data[2],
                    'house_size': del_data[3],
                    'house_towards': del_data[4],
                    'house_flood': del_data[5],
                    'house_year': del_data[6],
                    'house_building': del_data[7],
                    'house_total_price': del_data[8],
                    'house_unit_price': del_data[9],
                    'house_date_price': del_data[10],
                    'date': date
                })
                
                db.deleteHouse(item[0])
                logger.debug(f"  售出房源: {item[0]}")
    
    except Exception as e:
        logger.error(f"  处理售出房源失败: {e}", exc_info=True)
    
    return stats


def print_summary(date, stats):
    """打印统计摘要"""
    logger = get_logger()
    
    logger.info("")
    logger.info("=" * 60)
    logger.info(f"日期: {date}")
    logger.info("=" * 60)
    
    logger.info("")
    logger.info("📊 统计摘要:")
    logger.info(f"  新增: {stats['new_count']} 套")
    logger.info(f"  变动: {stats['change_count']} 套")
    logger.info(f"  减少: {stats['delete_count']} 套")
    
    if stats['new_list']:
        logger.info("")
        logger.info("🆕 新增房源:")
        for i, url in enumerate(stats['new_list'][:5], 1):
            logger.info(f"  {i}. {url}")
        if len(stats['new_list']) > 5:
            logger.info(f"  ... 还有 {len(stats['new_list']) - 5} 套")
    
    if stats['change_list']:
        logger.info("")
        logger.info("💰 价格变动:")
        for i, url in enumerate(stats['change_list'][:5], 1):
            logger.info(f"  {i}. {url}")
        if len(stats['change_list']) > 5:
            logger.info(f"  ... 还有 {len(stats['change_list']) - 5} 套")
    
    if stats['delete_list']:
        logger.info("")
        logger.info("❌ 已售出:")
        for i, url in enumerate(stats['delete_list'][:5], 1):
            logger.info(f"  {i}. {url}")
        if len(stats['delete_list']) > 5:
            logger.info(f"  ... 还有 {len(stats['delete_list']) - 5} 套")
    
    logger.info("")
    logger.info("=" * 60)


def main():
    """主函数"""
    # 初始化日志系统
    setup_logger(
        log_dir=sys.path[0] + '/../logs',
        log_level=logging.INFO,  # 可改为 logging.DEBUG 查看详细信息
        console_output=True
    )
    
    logger = get_logger()
    
    try:
        # 加载配置
        config_path = sys.path[0] + '/../config/config.json'
        config = load_config(config_path)
        
        # 批量抓取数据
        all_data = fetch_all_data(config)
        
        if not all_data:
            logger.error("❌ 错误: 未获取到任何数据")
            sys.exit(1)
        
        # 初始化数据库
        logger.info("初始化数据库连接...")
        db = Database()
        
        # 获取当前日期
        date = datetime.today().strftime('%Y-%m-%d')
        
        # 处理数据
        stats = process_houses(all_data, db, config, date)
        
        # 打印摘要
        print_summary(date, stats)
        
        # 确保数据保存
        try:
            db.conn.commit()
            logger.info("数据库提交成功")
        except Exception as e:
            logger.error(f"⚠ 数据库提交失败: {e}", exc_info=True)
        
        logger.info("")
        logger.info("程序执行完成!")
        
    except Exception as e:
        logger.critical(f"程序执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
