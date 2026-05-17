#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
为存量小区生成通勤缓存，并回填 HOUSE 表冗余通勤时长。
"""

import logging
import os
import sys

from commute_service import CommuteService
from database import Database
from logger import get_logger, setup_logger
from main import load_config


def main():
    setup_logger(
        log_dir=sys.path[0] + '/../logs',
        log_level=logging.INFO,
        console_output=True
    )
    logger = get_logger()

    try:
        config_path = os.path.join(sys.path[0], '..', 'config', 'config.json')
        config = load_config(config_path)

        db = Database(workplaces=config.get('workplaces'))
        commute_service = CommuteService(db=db, config=config, logger=logger)

        commute_service.sync_all_houses()
        db.conn.commit()
        logger.info('小区通勤信息回填完成')

    except Exception as exc:
        logger.critical(f'生成通勤信息失败: {exc}', exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
