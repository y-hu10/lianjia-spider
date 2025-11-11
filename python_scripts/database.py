#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修复后的 database.py - 解决 SQL 注入问题
"""

import sqlite3
import json
import sys
from datetime import datetime


class Database:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = sys.path[0] + '/../db/lianjia.db'
        
        self.conn = sqlite3.connect(db_path)
        self.c = self.conn.cursor()
        
        self.__createHouseTable()
        self.__createSellOutTable()

    def __del__(self):
        try:
            self.conn.commit()
            self.conn.close()
        except:
            pass

    def __createHouseTable(self):
        self.c.execute('''
        CREATE TABLE IF NOT EXISTS HOUSE (
            ID             INT      PRIMARY KEY     NOT NULL,
            LOCATION       TEXT                     NOT NULL,
            TYPE           TEXT                     NOT NULL,
            SIZE           TEXT                     NOT NULL,
            TOWARDS        TEXT                     NOT NULL,
            FLOOD          TEXT                     NOT NULL,
            YEAR           TEXT                     NOT NULL,
            BUILDING       TEXT                     NOT NULL,
            TOTAL_PRICE    TEXT                     NOT NULL,
            UNIT_PRICE     TEXT                     NOT NULL,
            DATE_PRICE     TEXT                     NOT NULL,
            REGION         TEXT                     NOT NULL
        );
        ''')

    def __createSellOutTable(self):
        self.c.execute('''
        CREATE TABLE IF NOT EXISTS SELLOUT (
            ID             INT      PRIMARY KEY     NOT NULL,
            LOCATION       TEXT                     NOT NULL,
            TYPE           TEXT                     NOT NULL,
            SIZE           TEXT                     NOT NULL,
            TOWARDS        TEXT                     NOT NULL,
            FLOOD          TEXT                     NOT NULL,
            YEAR           TEXT                     NOT NULL,
            BUILDING       TEXT                     NOT NULL,
            TOTAL_PRICE    TEXT                     NOT NULL,
            UNIT_PRICE     TEXT                     NOT NULL,
            DATE_PRICE     TEXT                     NOT NULL,
            DATE           TEXT                     NOT NULL,
            REGION         TEXT                     NOT NULL
        );
        ''')
    
    def insertHouse(self, house):
        """插入房源 - 使用参数化查询防止SQL注入"""
        self.c.execute(
            "INSERT INTO HOUSE (ID,LOCATION,TYPE,SIZE,TOWARDS,FLOOD,YEAR,BUILDING,TOTAL_PRICE,UNIT_PRICE,DATE_PRICE,REGION) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                house['house_id'],
                house['house_location'],
                house['house_type'],
                house['house_size'],
                house['house_towards'],
                house['house_flood'],
                house['house_year'],
                house['house_building'],
                house['house_total_price'],
                house['house_unit_price'],
                house['house_date_price'],
                house['house_region']
            )
        )

    def updateHouse(self, house):
        """更新房源 - 使用参数化查询防止SQL注入"""
        self.c.execute(
            "UPDATE HOUSE SET TOTAL_PRICE=?, UNIT_PRICE=?, DATE_PRICE=? WHERE ID=?",
            (
                house['house_total_price'],
                house['house_unit_price'],
                house['house_date_price'],
                house['house_id']
            )
        )

    def selectHouse(self, house_id):
        """查询房源 - 修复SQL注入漏洞"""
        return self.c.execute("SELECT * FROM HOUSE WHERE ID=?", (house_id,))

    def deleteHouse(self, house_id):
        """删除房源 - 修复SQL注入漏洞"""
        self.c.execute("DELETE FROM HOUSE WHERE ID=?", (house_id,))

    def countHouse(self):
        """统计房源数量"""
        return self.c.execute('''SELECT count() FROM HOUSE''').fetchone()[0]

    def findAllSellOutFromHouse(self, date):
        """查找所有在指定日期未更新的房源（可能已售出）"""
        return self.c.execute(
            "SELECT * FROM HOUSE WHERE DATE_PRICE NOT LIKE ?",
            ('%' + date + '%',)
        )

    def insertSellOut(self, house):
        """插入已售出房源 - 使用参数化查询防止SQL注入"""
        self.c.execute(
            "INSERT INTO SELLOUT (ID,LOCATION,TYPE,SIZE,TOWARDS,FLOOD,YEAR,BUILDING,TOTAL_PRICE,UNIT_PRICE,DATE_PRICE,DATE,REGION) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                house['house_id'],
                house['house_location'],
                house['house_type'],
                house['house_size'],
                house['house_towards'],
                house['house_flood'],
                house['house_year'],
                house['house_building'],
                house['house_total_price'],
                house['house_unit_price'],
                house['house_date_price'],
                house['date'],
                house['house_region']
            )
        )

    def selectSellOut(self, house_id):
        """查询已售出房源 - 修复SQL注入漏洞"""
        return self.c.execute("SELECT * FROM SELLOUT WHERE ID=?", (house_id,))
