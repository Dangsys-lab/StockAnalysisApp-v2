# -*- coding: utf-8 -*-
"""
自选股数据模型与数据库管理

功能:
- SQLite数据库初始化
- 自选股数据表结构定义
- CRUD基础操作

合规声明:
本模块仅提供用户自选股票的数据存储功能。
不包含任何投资建议或推荐内容。
"""

import sqlite3
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple


class PortfolioDatabase:
    """
    自选股数据库管理器
    
    使用SQLite本地存储用户的自选股票列表
    支持分组、备注、添加记录等功能
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(base_dir, 'data')
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, 'portfolio.db')
        
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA encoding = 'UTF-8'")
        self._initialize_database()
    
    def _get_connection(self) -> sqlite3.Connection:
        return self._conn
    
    def _initialize_database(self):
        """初始化数据库表结构"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT NOT NULL UNIQUE,
                stock_name TEXT,
                group_name TEXT DEFAULT '默认',
                note TEXT DEFAULT '',
                add_date TEXT DEFAULT (datetime('now', 'localtime')),
                add_price REAL DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolio_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id INTEGER,
                action_type TEXT NOT NULL,
                price REAL,
                quantity INTEGER DEFAULT 0,
                note TEXT DEFAULT '',
                record_date TEXT DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (portfolio_id) REFERENCES portfolio(id)
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_portfolio_code ON portfolio(stock_code)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_portfolio_group ON portfolio(group_name)')
        
        conn.commit()
    
    def add_stock(self, stock_code: str, stock_name: str = '', group_name: str = '默认',
                  note: str = '', add_price: float = 0.0) -> Dict[str, Any]:
        """添加自选股票"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
                INSERT OR REPLACE INTO portfolio 
                (stock_code, stock_name, group_name, note, add_price, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (stock_code, stock_name, group_name, note, add_price, now))
            
            portfolio_id = cursor.lastrowid
            
            cursor.execute('''
                INSERT INTO portfolio_history 
                (portfolio_id, action_type, price, note, record_date)
                VALUES (?, 'ADD', ?, ?, ?)
            ''', (portfolio_id, add_price, f'添加到{group_name}', now))
            
            conn.commit()
            
            return {'success': True, 'id': portfolio_id, 'stock_code': stock_code, 'message': '已添加到自选列表'}
        
        except Exception as e:
            return {'success': False, 'error': str(e), 'message': f'添加失败: {str(e)}'}
    
    def remove_stock(self, stock_code: str) -> Dict[str, Any]:
        """移除自选股票"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT id FROM portfolio WHERE stock_code = ?', (stock_code,))
            row = cursor.fetchone()
            
            if row:
                portfolio_id = row['id']
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('INSERT INTO portfolio_history (portfolio_id, action_type, record_date) VALUES (?, "REMOVE", ?)',
                               (portfolio_id, now))
            
            cursor.execute('DELETE FROM portfolio WHERE stock_code = ?', (stock_code,))
            conn.commit()
            
            return {'success': True, 'stock_code': stock_code, 'message': '已从自选列表移除'}
        
        except Exception as e:
            return {'success': False, 'error': str(e), 'message': f'移除失败: {str(e)}'}
    
    def update_stock(self, stock_code: str, **kwargs) -> Dict[str, Any]:
        """更新自选股票信息"""
        try:
            valid_fields = ['stock_name', 'group_name', 'note', 'add_price']
            updates = {k: v for k, v in kwargs.items() if k in valid_fields and v is not None}
            
            if not updates:
                return {'success': False, 'message': '没有有效的更新字段'}
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            set_clause = ', '.join([f'{k} = ?' for k in updates.keys()])
            values = list(updates.values()) + [stock_code]
            
            cursor.execute(f'UPDATE portfolio SET {set_clause}, updated_at = ? WHERE stock_code = ?',
                           values + [datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
            
            conn.commit()
            
            return {'success': True, 'updated_fields': list(updates.keys()), 'message': '更新成功'}
        
        except Exception as e:
            return {'success': False, 'error': str(e), 'message': f'更新失败: {str(e)}'}
    
    def get_stock(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取单只自选股票详情"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM portfolio WHERE stock_code = ?', (stock_code,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            print(f"查询失败: {e}")
            return None
    
    def get_all_stocks(self, group_name: str = None, sort_by: str = 'add_date', order: str = 'DESC') -> List[Dict[str, Any]]:
        """获取所有自选股票列表"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            query = 'SELECT * FROM portfolio'
            params = []
            
            if group_name:
                query += ' WHERE group_name = ?'
                params.append(group_name)
            
            allowed_sort = ['add_date', 'stock_code', 'stock_name', 'add_price', 'updated_at']
            sort_by = sort_by if sort_by in allowed_sort else 'add_date'
            order = order.upper() if order.upper() in ['ASC', 'DESC'] else 'DESC'
            query += f' ORDER BY {sort_by} {order}'
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        
        except Exception as e:
            print(f"查询列表失败: {e}")
            return []
    
    def get_groups(self) -> List[Dict[str, Any]]:
        """获取所有分组及其数量"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT group_name, COUNT(*) as count FROM portfolio GROUP BY group_name ORDER BY count DESC')
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"获取分组失败: {e}")
            return [{'group_name': '默认', 'count': 0}]
    
    def get_count(self, group_name: str = None) -> int:
        """获取自选股票数量"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if group_name:
                cursor.execute('SELECT COUNT(*) as count FROM portfolio WHERE group_name = ?', (group_name,))
            else:
                cursor.execute('SELECT COUNT(*) as count FROM portfolio')
            
            result = cursor.fetchone()
            return result['count'] if result else 0
        except Exception as e:
            print(f"统计数量失败: {e}")
            return 0
    
    def check_exists(self, stock_code: str) -> bool:
        """检查股票是否已在自选中"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM portfolio WHERE stock_code = ?', (stock_code,))
            return cursor.fetchone() is not None
        except Exception as e:
            print(f"检查存在性失败: {e}")
            return False


if __name__ == '__main__':
    print("=" * 60)
    print("自选股数据库测试")
    print("=" * 60)
    
    db = PortfolioDatabase(':memory:')
    
    r1 = db.add_stock('600519', '贵州茅台', '白酒龙头', '优质白马', 1800.00)
    print(f"\n添加600519: {r1['message']}")
    
    r2 = db.add_stock('000858', '五粮液', '白酒', '', 200.00)
    print(f"添加000858: {r2['message']}")
    
    stock = db.get_stock('600519')
    if stock:
        print(f"\n600519详情: {stock['stock_name']} - {stock['group_name']}")
    
    print(f"\n总数量: {db.get_count()}")
    
    groups = db.get_groups()
    for g in groups:
        print(f"  分组 '{g['group_name']}': {g['count']}只")
    
    all_stocks = db.get_all_stocks(sort_by='stock_code')
    print(f"\n所有股票:")
    for s in all_stocks:
        print(f"  - {s['stock_code']} {s['stock_name']} ({s['group_name']})")
    
    r4 = db.update_stock('600519', note='更新后的备注', add_price=1850.00)
    print(f"\n更新600519: {r4['message']}")
    
    exists = db.check_exists('600519')
    print(f"600519是否存在: {exists}")
    
    r5 = db.remove_stock('000858')
    print(f"删除000858: {r5['message']}")
    
    print(f"\n删除后数量: {db.get_count()}")
    
    print("\n✅ 自选股数据库功能正常")
