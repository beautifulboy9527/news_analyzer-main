"""
新闻数据存储

负责保存和加载新闻数据。
"""

import os
import json
import logging
import shutil
import sqlite3
import threading
from typing import List, Dict, Optional, Any, Tuple, Union
from datetime import datetime, timedelta
from src.models import NewsArticle # Commented out, will handle data as dicts for now


def convert_datetime_to_iso(obj):
    """递归转换数据结构中的 datetime 对象为 ISO 格式字符串"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: convert_datetime_to_iso(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_datetime_to_iso(item) for item in obj]
    return obj


class NewsStorage:
    """新闻数据存储类 - 使用 SQLite"""

    DB_FILE_NAME = "news_data.db"
    # HISTORY_FILE_NAME = "browsing_history.json" # Removed
    # READ_STATUS_FILE_NAME = "read_status.json" # Removed
    # MAX_HISTORY_ITEMS = 1000 # Removed, DB will handle limits if necessary via queries

    def __init__(self, data_dir: str = "data", db_name: Optional[str] = None, ddl_file_path: Optional[str] = None): # Added db_name for testing
        """初始化存储器

        Args:
            data_dir: 数据存储目录
            db_name: 数据库文件名 (主要用于测试, 默认为 DB_FILE_NAME)
            ddl_file_path: DDL 文件路径 (主要用于测试, 默认为 None)
        """
        self.logger = logging.getLogger('news_analyzer.storage')
        self.lock = threading.RLock()

        # 优先使用相对路径，兼容运行位置
        # Assuming the script is run from the project root or src/
        # Adjusting path resolution logic slightly
        current_script_path = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_script_path) # Up one level from src/storage to src/
        project_root = os.path.dirname(project_root) # Up one level from src/ to project root

        self.data_dir = os.path.join(project_root, data_dir)
        
        # 如果上述路径不存在，尝试使用绝对路径
        if not os.path.exists(self.data_dir):
             self.data_dir = os.path.abspath(data_dir) # Fallback to absolute if initial relative fails

        self._ensure_dir(self.data_dir)
        # self._ensure_dir(os.path.join(self.data_dir, "news")) # Removed, news stored in DB
        # self._ensure_dir(os.path.join(self.data_dir, "analysis")) # Removed, analysis stored in DB

        if db_name == ":memory:":
            self.db_path = ":memory:"
        else:
            self.db_path = os.path.join(self.data_dir, db_name if db_name else self.DB_FILE_NAME)
        
        self.logger.info(f"数据存储目录 (仅当 db_path 不是 :memory: 时相关): {self.data_dir if self.db_path != ':memory:' else 'N/A'}")
        self.logger.info(f"SQLite 数据库路径: {self.db_path}")

        self.conn: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None
        
        self._db_just_created = False # Initialize the flag
        self.actual_ddl_file_path = ddl_file_path if ddl_file_path else os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "docs", "development", "logic", "database_schema.sql"
        ) # Determine actual DDL path or use default

        if hasattr(self, '_skip_db_setup_for_mock_tests') and self._skip_db_setup_for_mock_tests:
            self.logger.warning(
                f"Skipping DB connect and table creation due to _skip_db_setup_for_mock_tests=True. DB path: {self.db_path}"
            )
            return # Exit early if skipping setup for tests

        db_file_exists_prior_to_init = self.db_path != ":memory:" and os.path.exists(self.db_path)

        try:
            self._connect_db() # Always attempt to connect first

            # --- Try to add new columns if they don't exist (for existing DBs) ---
            if db_file_exists_prior_to_init: # Only try ALTER if the DB file already existed
                self.logger.info("尝试为现有数据库添加新列 (如果不存在)...")
                columns_to_add = {
                    "status": "TEXT DEFAULT 'unknown'",
                    "last_error": "TEXT",
                    "consecutive_error_count": "INTEGER DEFAULT 0"
                }
                for col_name, col_def in columns_to_add.items():
                    try:
                        self.cursor.execute(f"ALTER TABLE news_sources ADD COLUMN {col_name} {col_def}")
                        self.logger.info(f"成功添加列 '{col_name}' 到 news_sources 表。")
                    except sqlite3.OperationalError as e:
                        if f"duplicate column name: {col_name}" in str(e):
                            self.logger.debug(f"列 '{col_name}' 已存在于 news_sources 表。")
                        else:
                            self.logger.error(f"尝试添加列 '{col_name}' 时发生错误: {e}", exc_info=True)
                            # Depending on severity, might want to raise here
                    except sqlite3.Error as e_generic: # Catch other potential SQLite errors
                         self.logger.error(f"尝试添加列 '{col_name}' 时发生 SQLite 错误: {e_generic}", exc_info=True)

                try:
                    self.conn.commit() # Commit the ALTER TABLE statements if any succeeded
                except sqlite3.Error as e_commit:
                     self.logger.error(f"提交 ALTER TABLE 语句时出错: {e_commit}")
            # --- End column addition ---

            if not db_file_exists_prior_to_init: # If DB file did NOT exist (or is memory db)
                self.logger.info(f"数据库文件未找到于 {self.db_path} (或为内存数据库)。正在创建表...")
                if self.conn: # Ensure connection was successful before trying to create tables
                    self._create_tables(ddl_file_path=self.actual_ddl_file_path)
                    self._db_just_created = True # Set flag indicating DB (and tables) were newly created
                else:
                    # This case should ideally be caught by _connect_db raising an error, but as a safeguard:
                    self.logger.error("Cannot create tables: Database connection failed and no exception was propagated from _connect_db.")
                    raise sqlite3.OperationalError("Failed to connect to DB, cannot proceed with table creation.") # Critical
            else: # DB file already existed
                 self.logger.info(f"Database file already exists at {self.db_path}. Tables will not be recreated.")
                 # Future: Add schema version check and migration logic here if needed.
        
        except sqlite3.Error as e: # Catch SQLite specific errors from _connect_db or _create_tables
            self.logger.error(f"SQLite error during NewsStorage setup for {self.db_path}: {e}", exc_info=True)
            if self.conn: self.conn.close() # Attempt to clean up connection
            raise # Re-raise to signal critical failure to the caller
        except Exception as e_global: # Catch any other unexpected errors
            self.logger.error(f"Unexpected critical error during NewsStorage setup for {self.db_path}: {e_global}", exc_info=True)
            if self.conn: self.conn.close()
            raise
        
        self.logger.info(f"NewsStorage initialized. DB path: {self.db_path}, DB file existed prior: {db_file_exists_prior_to_init}, DB (tables) just created now: {self._db_just_created}")

    def was_db_just_created(self) -> bool:
        """Returns True if the database tables were created during this NewsStorage instance's initialization."""
        return self._db_just_created

    def _ensure_dir(self, directory: str):
        """确保目录存在

        Args:
            directory: 目录路径
        """
        if not os.path.exists(directory):
            os.makedirs(directory)
            self.logger.info(f"创建目录: {directory}")

    def _connect_db(self): # Added method
        """连接到 SQLite 数据库并设置 cursor"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row # Access columns by name
            self.conn.execute("PRAGMA foreign_keys = ON;") # Enforce foreign key constraints
            self.cursor = self.conn.cursor()
            self.logger.info(f"成功连接到 SQLite 数据库: {self.db_path}")
        except sqlite3.Error as e:
            self.logger.error(f"连接 SQLite 数据库失败 {self.db_path}: {e}", exc_info=True)
            self.conn = None
            self.cursor = None
            raise # Re-raise the exception to signal a critical failure

    def _create_tables(self, ddl_file_path: Optional[str] = None): # Added method
        """从 DDL 文件创建数据库表 (如果不存在)"""
        self.logger.info(">>> _create_tables: 方法开始执行") # 新增
        if not self.conn or not self.cursor:
            self.logger.error("_create_tables: 数据库未连接，无法创建表")
            return

        # Determine DDL file path relative to this file's location
        # Assumes database_schema.sql is in docs/development/logic/
        # Path from src/storage/news_storage.py to project_root is already calculated
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ddl_file_path = ddl_file_path if ddl_file_path else os.path.join(project_root, "docs", "development", "logic", "database_schema.sql")

        if not os.path.exists(ddl_file_path):
            self.logger.error(f"数据库 DDL 文件未找到: {ddl_file_path}")
            # If it's an in-memory database for testing, maybe we don't strictly need the schema
            # if the tests are mocking the methods that interact with tables.
            if self.db_path == ":memory:":
                self.logger.warning("正在使用内存数据库且 DDL 文件未找到。表可能未创建。如果测试 mock 了数据库交互，这可能不是问题。")
                return # Allow continuation for in-memory DB if DDL is missing
            raise FileNotFoundError(f"Database schema DDL file not found: {ddl_file_path}")

        try:
            with open(ddl_file_path, 'r', encoding='utf-8') as f:
                ddl_content = f.read()
            self.logger.debug(f"_create_tables: 从 {ddl_file_path} 读取到的 DDL 内容 (前500字符):\n{ddl_content[:500]}") # 新增
            
            # --- 关键步骤：移除了在执行 DDL 之前删除旧表的逻辑 ---
            # self.logger.info(f"_create_tables: 准备在执行DDL之前清空 news_sources 和 articles 表 (如果存在)") # Log change

            # self.logger.info("_create_tables: 开始执行 DROP TABLE IF EXISTS news_sources;") # ADDED
            # self.cursor.execute("DROP TABLE IF EXISTS news_sources;")
            # self.logger.info("_create_tables: DROP TABLE IF EXISTS news_sources; 执行完毕.") # ADDED

            # self.logger.info("_create_tables: 开始执行 DROP TABLE IF EXISTS articles;") # ADDED
            # self.cursor.execute("DROP TABLE IF EXISTS articles;") # 为了彻底，也清空文章表
            # self.logger.info("_create_tables: DROP TABLE IF EXISTS articles; 执行完毕.") # ADDED
            # # self.cursor.execute("DROP TABLE IF EXISTS browsing_history;") # 如果需要，也可以清空其他表
            # # self.cursor.execute("DROP TABLE IF EXISTS llm_analyses;")
            # # self.cursor.execute("DROP TABLE IF EXISTS article_analysis_mappings;")

            # self.logger.info("_create_tables: 开始执行 conn.commit() 在 DROP 之后;") # ADDED
            # self.conn.commit() # 确保 DROP 生效
            # self.logger.info("_create_tables: conn.commit() 在 DROP 之后执行完毕.") # ADDED
            
            # self.logger.info(f"_create_tables: 旧表清理完成。现在从 DDL 文件执行建表语句: {ddl_file_path}") # Log change
            self.logger.info(f"_create_tables: 现在将直接从 DDL 文件执行建表语句 (CREATE TABLE IF NOT EXISTS): {ddl_file_path}")


            # --- 清理结束 ---

            self.logger.info(f"_create_tables: 开始执行 self.cursor.executescript(ddl_content) from {ddl_file_path}") # ADDED
            self.cursor.executescript(ddl_content) # 执行DDL脚本
            self.logger.info("_create_tables: self.cursor.executescript(ddl_content) 执行完毕.") # ADDED

            self.logger.info("_create_tables: 开始执行 conn.commit() 在 executescript 之后;") # ADDED
            self.conn.commit()
            self.logger.info("_create_tables: conn.commit() 在 executescript 之后执行完毕.") # ADDED
            
            self.logger.info(f"_create_tables: 已成功从 {ddl_file_path} 执行数据库 DDL 脚本.")

            # 验证表是否创建成功 (可选的调试步骤)
            self.logger.info("_create_tables: 开始验证 news_sources 表结构") # ADDED
            self.cursor.execute("PRAGMA table_info(news_sources);")
            columns = self.cursor.fetchall()
            self.logger.info(f"_create_tables: PRAGMA table_info(news_sources) -> {columns}") # ADDED
            if not any(col['name'] == 'notes' for col in columns): # ADDED
                 self.logger.error("_create_tables: CRITICAL - 表 news_sources 创建后仍然缺少 'notes' 字段!") # ADDED


        except sqlite3.Error as e:
            self.logger.error(f"_create_tables: 从 DDL 文件创建表时发生 SQLite 错误: {e}", exc_info=True)
            # 根据错误处理策略，可能需要回滚或抛出异常
        except FileNotFoundError: # 已在前面处理，但以防万一
             self.logger.error(f"_create_tables: DDL 文件未找到 (在 try 块中再次捕获): {ddl_file_path}") # Log change
        except Exception as e_global: # 捕获其他可能的异常 # ADDED
            self.logger.error(f"_create_tables: 发生未知错误: {e_global}", exc_info=True) # ADDED
        finally: # ADDED
            self.logger.info("<<< _create_tables: 方法执行完毕") # ADDED

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            try:
                self.conn.close()
                self.logger.info("SQLite 数据库连接已关闭.")
            except sqlite3.Error as e:
                self.logger.error(f"关闭数据库连接时出错: {e}", exc_info=True)
            finally:
                self.conn = None
                self.cursor = None
        else:
            self.logger.info("数据库连接已经关闭或从未打开.")

    def _article_from_row(self, row: sqlite3.Row) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        
        article_dict = dict(row) # Convert sqlite3.Row to a dictionary

        # Convert datetime strings to datetime objects
        for key in ["publish_time", "retrieval_time"]:
            if article_dict.get(key) and isinstance(article_dict[key], str):
                date_str = article_dict[key]
                parsed_dt = None
                try:
                    # 优先尝试 fromisoformat，因为它更严格且通常更快
                    parsed_dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except ValueError:
                    # 如果 fromisoformat 失败，回退到更宽松的 dateutil.parser
                    try:
                        # Import parser here to avoid circular dependency or making it a class member if not broadly used
                        from dateutil import parser as dateutil_parser 
                        parsed_dt = dateutil_parser.parse(date_str)
                        # dateutil.parser might return a naive datetime, ensure timezone if needed
                        # For now, we assume that if it's parsed, it's what we want.
                        # If specific timezone handling (e.g., assuming UTC if naive) is required here,
                        # it should be consistent with how AppService handles it.
                        # However, storage layer should ideally just store and retrieve.
                    except (ValueError, TypeError, OverflowError) as e_dateutil:
                        self.logger.warning(f"宽松日期解析 (dateutil) 失败 for key '{key}': {date_str} in article ID {article_dict.get('id')}. Error: {e_dateutil}")
                        parsed_dt = None 
                    except Exception as e_general_dateutil: # Catch any other parsing error
                        self.logger.error(f"宽松日期解析 (dateutil) 出现未知错误 for key '{key}': {date_str}. Error: {e_general_dateutil}", exc_info=True)
                        parsed_dt = None
                
                article_dict[key] = parsed_dt # Assign whatever was parsed (or None if all failed)

        # Ensure is_read is boolean (it's stored as INTEGER 0 or 1)
        if "is_read" in article_dict:
            article_dict["is_read"] = bool(article_dict["is_read"])
            
        return article_dict

    def upsert_article(self, article_data: Dict[str, Any]) -> Optional[int]:
        """
        Inserts a new article or updates an existing one based on the 'link' unique constraint.
        Expected keys in article_data: title, content, link, source_name, source_url, 
                                       publish_time, category_name, image_url.
        Optional keys: is_read (defaults to 0), llm_summary.
        retrieval_time is automatically set.
        Returns the id of the inserted/updated row, or None on failure.
        """
        if not self.conn or not self.cursor:
            self.logger.error("Database not connected. Cannot upsert article.")
            return None
        if 'link' not in article_data or not article_data['link']:
            self.logger.error("Cannot upsert article: 'link' is missing or empty.")
            return None

        # Ensure retrieval_time is set
        article_data.setdefault('retrieval_time', datetime.now().isoformat())
        article_data.setdefault('is_read', 0) # Default is_read to False (0)
        article_data.setdefault('title', None)
        article_data.setdefault('content', None)
        article_data.setdefault('source_name', None)
        article_data.setdefault('source_url', None)
        article_data.setdefault('publish_time', None)
        article_data.setdefault('category_name', None)
        article_data.setdefault('image_url', None)
        article_data.setdefault('llm_summary', None)


        # Columns for INSERT and UPDATE
        # id is autoincrement, not included in insert list
        cols = [
            'title', 'content', 'link', 'source_name', 'source_url', 
            'publish_time', 'retrieval_time', 'category_name', 'image_url', 
            'is_read', 'llm_summary'
        ]
        
        sql = f"""
            INSERT INTO articles ({', '.join(cols)})
            VALUES ({', '.join([':' + col for col in cols])})
            ON CONFLICT(link) DO UPDATE SET
                title=excluded.title,
                content=excluded.content,
                source_name=excluded.source_name,
                source_url=excluded.source_url,
                publish_time=excluded.publish_time,
                retrieval_time=excluded.retrieval_time, 
                category_name=excluded.category_name,
                image_url=excluded.image_url,
                is_read=excluded.is_read, 
                llm_summary=excluded.llm_summary
            RETURNING id; 
        """
        # RETURNING id is SQLite 3.35.0+
        # For older versions, we'd have to do a SELECT last_insert_rowid() or get_article_by_link

        try:
            # Filter article_data to only include keys that are columns
            params = {key: article_data.get(key) for key in cols}

            self.cursor.execute(sql, params)
            inserted_id = self.cursor.fetchone()
            self.conn.commit()
            
            if inserted_id:
                self.logger.debug(f"Article upserted/updated with link '{article_data['link']}', ID: {inserted_id[0]}.")
                return inserted_id[0]
            else: # Fallback if RETURNING id is not supported or fails (should not happen with modern SQLite)
                 # This part is a fallback, might need testing if SQLite version is very old.
                self.logger.warning(f"Article upserted/updated with link '{article_data['link']}', but ID not returned by RETURNING. Attempting to fetch by link.")
                res = self.get_article_by_link(article_data['link'])
                return res['id'] if res else None

        except sqlite3.Error as e:
            self.logger.error(f"Failed to upsert article with link '{article_data['link']}': {e}", exc_info=True)
            try:
                self.conn.rollback()
            except sqlite3.Error as re:
                self.logger.error(f"Rollback failed: {re}", exc_info=True)
            return None

    def upsert_articles_batch(self, articles_data: List[Dict[str, Any]]) -> int:
        """
        Upserts a list of articles in a batch.
        Returns the number of rows affected (sum of changes for insert/update).
        """
        if not self.conn or not self.cursor:
            self.logger.error("Database not connected. Cannot upsert articles batch.")
            return 0
        if not articles_data:
            self.logger.info("No articles provided for batch upsert.")
            return 0

        # Columns for INSERT and UPDATE
        cols = [
            'title', 'content', 'link', 'source_name', 'source_url', 
            'publish_time', 'retrieval_time', 'category_name', 'image_url', 
            'is_read', 'llm_summary'
        ]
        
        sql = f"""
            INSERT INTO articles ({', '.join(cols)})
            VALUES ({', '.join([':' + col for col in cols])})
            ON CONFLICT(link) DO UPDATE SET
                title=excluded.title,
                content=excluded.content,
                source_name=excluded.source_name,
                source_url=excluded.source_url,
                publish_time=excluded.publish_time,
                retrieval_time=excluded.retrieval_time,
                category_name=excluded.category_name,
                image_url=excluded.image_url,
                is_read=excluded.is_read,
                llm_summary=excluded.llm_summary;
        """
        
        prepared_data = []
        for article_data in articles_data:
            if 'link' not in article_data or not article_data['link']:
                self.logger.warning(f"Skipping article in batch due to missing link: {article_data.get('title', 'N/A')}")
                continue
            
            # Ensure retrieval_time and defaults
            article_data.setdefault('retrieval_time', datetime.now().isoformat())
            article_data.setdefault('is_read', 0)
            # Add other setdefaults as in single upsert for consistency
            article_data.setdefault('title', None)
            article_data.setdefault('content', None)
            article_data.setdefault('source_name', None)
            article_data.setdefault('source_url', None)
            article_data.setdefault('publish_time', None)
            article_data.setdefault('category_name', None)
            article_data.setdefault('image_url', None)
            article_data.setdefault('llm_summary', None)

            params = {key: article_data.get(key) for key in cols}
            prepared_data.append(params)

        if not prepared_data:
            self.logger.info("No valid articles to process in batch after filtering.")
            return 0

        try:
            self.cursor.executemany(sql, prepared_data)
            # For executemany, rowcount gives the number of modified rows if the SQLite library was
            # compiled with SQLITE_ENABLE_BATCH_ATOMIC_WRITE and the underlying VFS supports it.
            # Otherwise, it might return -1 or the number of statements.
            # A more reliable way to get changes is to sum them up if needed, or check self.conn.changes()
            # For simplicity, we'll rely on cursor.rowcount if it's meaningful, or just commit.
            rows_affected = self.cursor.rowcount 
            self.conn.commit()
            self.logger.info(f"Batch upsert completed for {len(prepared_data)} articles. Rows affected (approx): {rows_affected if rows_affected != -1 else 'unknown'}. Total changes by connection: {self.conn.total_changes - self._initial_total_changes if hasattr(self, '_initial_total_changes') else 'N/A'}")
            # Store initial changes for next batch diff if needed more accurately
            # self._initial_total_changes = self.conn.total_changes 
            return rows_affected if rows_affected != -1 else len(prepared_data) # Return number of items attempted if rowcount is -1

        except sqlite3.Error as e:
            self.logger.error(f"Failed to batch upsert articles: {e}", exc_info=True)
            try:
                self.conn.rollback()
            except sqlite3.Error as re:
                self.logger.error(f"Rollback failed: {re}", exc_info=True)
            return 0

    def get_article_by_id(self, article_id: int) -> Optional[Dict[str, Any]]:
        """Fetches an article by its primary key ID."""
        if not self.conn or not self.cursor:
            self.logger.error("Database not connected. Cannot get article by ID.")
            return None
        try:
            self.cursor.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
            row = self.cursor.fetchone()
            return self._article_from_row(row)
        except sqlite3.Error as e:
            self.logger.error(f"Error fetching article by ID {article_id}: {e}", exc_info=True)
            return None

    def get_article_by_link(self, link: str) -> Optional[Dict[str, Any]]:
        """Fetches an article by its unique link."""
        if not self.conn or not self.cursor:
            self.logger.error("Database not connected. Cannot get article by link.")
            return None
        try:
            self.cursor.execute("SELECT * FROM articles WHERE link = ?", (link,))
            row = self.cursor.fetchone()
            return self._article_from_row(row)
        except sqlite3.Error as e:
            self.logger.error(f"Error fetching article by link '{link}': {e}", exc_info=True)
            return None

    def get_articles_by_links(self, links: List[str]) -> List[Dict[str, Any]]:
        """通过链接列表获取文章详情列表"""
        # self.logger.debug(f"get_articles_by_links: 尝试获取 {len(links)} 个链接的文章. Links: {links[:3]}...") # 减少日志冗余
        if not links:
            return []

        articles_dicts: List[Dict[str, Any]] = []

        placeholders = ",".join(["?"] * len(links))
        query = f"""
            SELECT * FROM articles 
            WHERE link IN ({placeholders})
        """
        # self.logger.debug(f"Executing query: {query} with links: {links}") # 减少日志冗余

        with self.lock: # Ensure thread safety
            if not self.conn or not self.cursor:
                self.logger.error("get_articles_by_links: 数据库未连接。")
                return [] # Or raise an exception
            
            try:
                # self.logger.debug(f"_get_connection_for_select: conn={self.conn}, cursor={self.cursor}") # 减少日志冗余
                self.cursor.execute(query, links)
                rows = self.cursor.fetchall()
                # self.logger.debug(f"Found {len(rows)} articles for links: {links[:3]}...") # 减少日志冗余

                for row in rows:
                    article_dict = self._article_from_row(row)
                    if article_dict: # _article_from_row can return None
                        articles_dicts.append(article_dict)
                        # self.logger.debug(f"  - Appended article: {article_dict.get('title')}") # 减少日志冗余
            
            except sqlite3.Error as e:
                self.logger.error(f"get_articles_by_links: 查询数据库时出错 (links: {links[:3]}...): {e}", exc_info=True)
                return [] 
            except Exception as e_global: 
                self.logger.error(f"get_articles_by_links: 发生未知错误 (links: {links[:3]}...): {e_global}", exc_info=True)
                return []

        # self.logger.debug(f"get_articles_by_links: 返回 {len(articles_dicts)} 个文章字典。") # 减少日志冗余
        return articles_dicts

    def get_all_articles(self, 
                         limit: Optional[int] = None, 
                         offset: Optional[int] = None,
                         sort_by: str = "publish_time", 
                         sort_desc: bool = True,
                         filter_is_read: Optional[bool] = None,
                         filter_category: Optional[str] = None,
                         search_term: Optional[str] = None,
                         search_fields: Optional[List[str]] = None,
                         ids: Optional[List[int]] = None, # Added ids filter
                         with_content: bool = True # Added with_content
                         ) -> List[Dict[str, Any]]:
        if not self.conn or not self.cursor:
            self.logger.error("数据库未连接，无法获取文章")
            return []

        select_columns = "*" if with_content else "id, title, link, source_name, source_url, publish_time, retrieval_time, category_name, image_url, is_read, llm_summary"
        base_query = f"SELECT {select_columns} FROM articles"
        
        conditions = []
        params: List[Any] = []

        if filter_is_read is not None:
            conditions.append("is_read = ?")
            params.append(1 if filter_is_read else 0)
        
        if filter_category:
            conditions.append("category_name = ?")
            params.append(filter_category)
        
        if ids:
            if not all(isinstance(i, int) for i in ids):
                self.logger.error("Invalid article IDs list provided for filtering.")
            else:
                conditions.append(f"id IN ({','.join(['?'] * len(ids))})")
                params.extend(ids)

        if search_term and search_fields:
            search_clauses = []
            for field in search_fields:
                # Basic validation for field names to prevent injection, though not strictly necessary with param queries
                if field in ["title", "content", "source_name", "category_name"]: # Whitelist fields
                    search_clauses.append(f"LOWER({field}) LIKE LOWER(?)")
                    params.append(f"%{search_term}%")
            if search_clauses:
                conditions.append(f"({' OR '.join(search_clauses)})")
        
        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)
        
        if sort_by: # Add basic validation for sort_by field
            valid_sort_columns = ["publish_time", "retrieval_time", "title", "source_name", "category_name", "id"]
            if sort_by not in valid_sort_columns:
                self.logger.warning(f"Invalid sort_by column: {sort_by}. Defaulting to 'publish_time'.")
                sort_by = "publish_time"
            base_query += f" ORDER BY {sort_by} {'DESC' if sort_desc else 'ASC'}"
        
        if limit is not None:
            base_query += " LIMIT ?"
            params.append(limit)
        
        if offset is not None:
            base_query += " OFFSET ?"
            params.append(offset)
            
        try:
            self.cursor.execute(base_query, params)
            rows = self.cursor.fetchall()
            return [self._article_from_row(row) for row in rows if row]
        except sqlite3.Error as e:
            self.logger.error(f"获取所有文章时出错: {e} (Query: {base_query}, Params: {params})", exc_info=True)
            return []

    def set_article_read_status(self, link: str, is_read: bool) -> bool:
        """Sets the is_read status for an article identified by its link."""
        if not self.conn or not self.cursor:
            self.logger.error("Database not connected. Cannot set article read status.")
            return False
        
        sql = "UPDATE articles SET is_read = :is_read WHERE link = :link"
        try:
            self.cursor.execute(sql, {"is_read": 1 if is_read else 0, "link": link})
            self.conn.commit()
            if self.cursor.rowcount > 0:
                self.logger.info(f"Set read status to {is_read} for article link '{link}'.")
                return True
            else:
                self.logger.warning(f"No article found with link '{link}' to update read status.")
                return False
        except sqlite3.Error as e:
            self.logger.error(f"Error setting read status for article link '{link}': {e}", exc_info=True)
            try:
                self.conn.rollback()
            except sqlite3.Error as re:
                self.logger.error(f"Rollback failed: {re}", exc_info=True)
            return False
            
    def get_total_articles_count(self, 
                                 filter_is_read: Optional[bool] = None,
                                 filter_category: Optional[str] = None,
                                 search_term: Optional[str] = None,
                                 search_fields: Optional[List[str]] = None,
                                 ids: Optional[List[int]] = None # Added ids filter
                                 ) -> int:
        if not self.conn or not self.cursor:
            self.logger.error("数据库未连接,无法获取文章总数")
            return 0

        base_query = "SELECT COUNT(*) FROM articles"
        conditions = []
        params: List[Any] = []

        if filter_is_read is not None:
            conditions.append("is_read = ?")
            params.append(1 if filter_is_read else 0)
        
        if filter_category:
            conditions.append("category_name = ?")
            params.append(filter_category)

        if ids:
            if not all(isinstance(i, int) for i in ids):
                self.logger.error("Invalid article IDs list provided for filtering count.")
            else:
                conditions.append(f"id IN ({','.join(['?'] * len(ids))})")
                params.extend(ids)

        if search_term and search_fields:
            search_clauses = []
            for field in search_fields:
                if field in ["title", "content", "source_name", "category_name"]: # Whitelist fields
                    search_clauses.append(f"LOWER({field}) LIKE LOWER(?)")
                    params.append(f"%{search_term}%")
            if search_clauses:
                conditions.append(f"({' OR '.join(search_clauses)})")
        
        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)
            
        try:
            self.cursor.execute(base_query, params)
            count = self.cursor.fetchone()
            return count[0] if count else 0
        except sqlite3.Error as e:
            self.logger.error(f"获取文章总数时出错: {e} (Query: {base_query}, Params: {params})", exc_info=True)
            return 0

    def is_item_read(self, item_link: str) -> bool:
        """Checks if an article with the given link is marked as read in the database."""
        if not item_link:
            return False
        article = self.get_article_by_link(item_link)
        if article:
            return bool(article.get("is_read", False))
        return False # Return False if article not found

    def add_read_item(self, item_link: str):
        """Marks an article with the given link as read in the database."""
        if item_link:
            self.logger.info(f"Marking item as read: {item_link}")
            self.set_article_read_status(item_link, True)
        else:
            self.logger.warning("Attempted to mark an item with an empty link as read.")

    def clear_all_read_status(self):
        """Marks all articles in the database as unread."""
        if not self.conn or not self.cursor:
            self.logger.error("Database not connected. Cannot clear all read status.")
            return False
        
        sql = "UPDATE articles SET is_read = 0 WHERE is_read = 1"
        try:
            self.cursor.execute(sql)
            self.conn.commit()
            self.logger.info(f"Cleared read status for {self.cursor.rowcount} articles.")
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Error clearing all read status: {e}", exc_info=True)
            try:
                self.conn.rollback()
            except sqlite3.Error as re:
                self.logger.error(f"Rollback failed: {re}", exc_info=True)
            return False

    def mark_item_as_unread(self, item_link: str):
        """Marks an article with the given link as unread in the database."""
        if not self.conn or not self.cursor:
            self.logger.error("Database not connected. Cannot mark item as unread.")
            return False
        
        sql = "UPDATE articles SET is_read = 0 WHERE link = :link"
        try:
            self.cursor.execute(sql, {"link": item_link})
            self.conn.commit()
            if self.cursor.rowcount > 0:
                self.logger.info(f"Marked item as unread: {item_link}")
                return True
            else:
                self.logger.warning(f"No article found with link '{item_link}' to mark as unread.")
                return False
        except sqlite3.Error as e:
            self.logger.error(f"Error marking item as unread: {e}", exc_info=True)
            try:
                self.conn.rollback()
            except sqlite3.Error as re:
                self.logger.error(f"Rollback failed: {re}", exc_info=True)
            return False

    def _history_entry_from_row(self, row: sqlite3.Row) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        
        entry_dict = dict(row)

        # Convert view_time string to datetime object
        if entry_dict.get("view_time") and isinstance(entry_dict["view_time"], str):
            try:
                entry_dict["view_time"] = datetime.fromisoformat(entry_dict["view_time"].replace('Z', '+00:00'))
            except ValueError:
                self.logger.warning(f"无效的日期时间格式 for 'view_time': {entry_dict['view_time']} in history ID {entry_dict.get('id')}")
                entry_dict["view_time"] = None
        
        # Populate article details if article_title, etc. are present from a JOIN
        # If not, they will remain as per the browsing_history table structure (i.e., not present)
        # This method now expects that if article details are needed, the query performs the JOIN.
        # Example: row might have 'article_title', 'article_link' from a JOIN.
        return entry_dict

    def add_browsing_history(self, article_id: int, view_time: Optional[datetime] = None) -> Optional[int]:
        if not self.conn or not self.cursor:
            self.logger.error("数据库未连接，无法添加浏览历史")
            return None

        if view_time is None:
            view_time = datetime.now()
        
        view_time_iso = view_time.isoformat()

        try:
            # First, check if the article_id exists in the articles table
            self.cursor.execute("SELECT id FROM articles WHERE id = ?", (article_id,))
            article_exists = self.cursor.fetchone()
            if not article_exists:
                self.logger.warning(f"尝试添加浏览历史失败: 文章 ID {article_id} 不存在于 articles 表中。")
                return None

            self.cursor.execute(
                "INSERT INTO browsing_history (article_id, view_time) VALUES (?, ?)",
                (article_id, view_time_iso)
            )
            self.conn.commit()
            history_id = self.cursor.lastrowid
            self.logger.info(f"已添加浏览历史，文章ID: {article_id}, 历史ID: {history_id}")
            return history_id
        except sqlite3.IntegrityError as ie:
             self.logger.error(f"添加浏览历史时发生完整性错误 (文章ID: {article_id}): {ie}. 可能article_id不存在或约束冲突。", exc_info=True)
             return None
        except sqlite3.Error as e:
            self.logger.error(f"添加浏览历史时出错 (文章ID: {article_id}): {e}", exc_info=True)
            return None

    def get_browsing_history(self, days_limit: Optional[int] = None, limit: Optional[int] = 100, offset: Optional[int] = 0) -> List[Dict[str, Any]]:
        """获取浏览历史记录，最新的在前面，包含文章详情。

        Args:
            days_limit (Optional[int]): 限制返回多少天内的历史记录。None 表示不限制天数。
            limit (Optional[int]): 返回记录的最大数量。
            offset (Optional[int]): 返回记录的偏移量。
        Returns:
            List[Dict[str, Any]]: 历史记录字典列表，每个字典包含文章详情。
        """
        if not self.conn or not self.cursor:
            self.logger.error("数据库未连接，无法获取浏览历史")
            return []

        base_sql = """
            SELECT 
                bh.id, 
                bh.view_time, 
                bh.article_id, 
                a.title AS article_title, 
                a.link AS article_link,
                a.source_name AS article_source_name,
                a.category_name AS article_category_name,
                a.publish_time AS article_publish_time,
                a.image_url AS article_image_url
            FROM browsing_history bh
            JOIN articles a ON bh.article_id = a.id
        """
        conditions = []
        params: List[Any] = []

        if days_limit is not None and days_limit > 0:
            cutoff_date_dt = datetime.now() - timedelta(days=days_limit)
            # Assuming view_time is stored as ISO8601 string.
            # SQLite can compare ISO8601 strings directly.
            conditions.append("bh.view_time >= ?")
            params.append(cutoff_date_dt.isoformat())
            self.logger.debug(f"Filtering browsing history for entries after {cutoff_date_dt.isoformat()}")


        if conditions:
            base_sql += " WHERE " + " AND ".join(conditions)
        
        base_sql += " ORDER BY bh.view_time DESC" # Order always applied

        if limit is not None:
            base_sql += " LIMIT ?"
            params.append(limit)
        if offset is not None and offset > 0: # Only add offset if it's greater than 0
            base_sql += " OFFSET ?"
            params.append(offset)
        
        try:
            self.logger.debug(f"Executing SQL for get_browsing_history: {base_sql} with params: {params}")
            self.cursor.execute(base_sql, params)
            rows = self.cursor.fetchall()
            return [self._history_entry_from_row(row) for row in rows if row]
        except sqlite3.Error as e:
            self.logger.error(f"获取浏览历史时出错: {e} (Query: {base_sql}, Params: {params})", exc_info=True)
            return []

    def delete_browsing_history_item(self, history_id: int) -> bool:
        """根据历史记录ID删除指定的浏览历史条目。"""
        if not self.conn or not self.cursor:
            self.logger.error("数据库未连接，无法删除浏览历史条目")
            return False
        try:
            self.cursor.execute("DELETE FROM browsing_history WHERE id = ?", (history_id,))
            self.conn.commit()
            if self.cursor.rowcount > 0:
                self.logger.info(f"已删除浏览历史条目 ID: {history_id}")
                return True
            else:
                self.logger.warning(f"未找到ID为 {history_id} 的浏览历史条目进行删除")
                return False
        except sqlite3.Error as e:
            self.logger.error(f"删除浏览历史条目 ID {history_id} 时出错: {e}", exc_info=True)
            return False

    def clear_all_browsing_history(self) -> bool:
        """Clears all entries from the browsing_history table."""
        if not self.conn or not self.cursor:
            self.logger.error("Database not connected. Cannot clear browsing history.")
            return False
        try:
            self.cursor.execute("DELETE FROM browsing_history")
            self.conn.commit()
            self.logger.info("All browsing history has been cleared.")
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Error clearing browsing history: {e}", exc_info=True)
            try:
                self.conn.rollback()
            except sqlite3.Error as re:
                self.logger.error(f"Rollback failed: {re}", exc_info=True)
            return False

    def get_all_news_sources(self) -> List[Dict[str, Any]]:
        """获取数据库中所有新闻源的配置"""
        try:
            self.cursor.execute("SELECT id, name, type, url, category_name, is_enabled, last_checked_time, custom_config, status, last_error, consecutive_error_count FROM news_sources") # +++ ADDED new fields
            rows = self.cursor.fetchall()
            # Convert rows (tuples) to dictionaries for easier use
            # Use description to get column names
            column_names = [description[0] for description in self.cursor.description]
            return [dict(zip(column_names, row)) for row in rows]
        except sqlite3.Error as e:
            self.logger.error(f"Error fetching all news sources: {e}")
            return []

    def add_news_source(self, source_data: Dict[str, Any]) -> Optional[int]:
        """Adds a new news source to the news_sources table.

        Args:
            source_data: A dictionary containing the news source data.
                         Expected keys: name, type, url (optional), category_name (optional),
                                        is_enabled (optional, defaults to True),
                                        custom_config (optional, defaults to {}),
                                        notes (optional), is_user_added (optional, defaults to True).

        Returns:
            The ID of the newly added news source, or None if an error occurred.
        """
        if not self.conn or not self.cursor:
            self.logger.error("Database not connected. Cannot add news source.")
            return None

        # Define expected columns (excluding 'id' as it's auto-increment)
        # Ensure these match your news_sources table schema from database_schema.sql
        cols = [
            'name', 'type', 'url', 'category_name', 'is_enabled',
            'custom_config', 'notes', 'is_user_added', 'last_checked_time'
        ]

        # Prepare parameters, ensuring all expected columns are present with defaults if necessary
        params = {}
        params['name'] = source_data.get('name')
        params['type'] = source_data.get('type')
        params['url'] = source_data.get('url') # Optional
        params['category_name'] = source_data.get('category_name', '未分类') # Default category
        params['is_enabled'] = bool(source_data.get('is_enabled', True))
        custom_config = source_data.get('custom_config', {})
        params['custom_config'] = json.dumps(custom_config) if isinstance(custom_config, dict) else custom_config
        params['notes'] = source_data.get('notes') # Optional
        params['is_user_added'] = bool(source_data.get('is_user_added', True))
        # last_checked_time can be None initially, or set to a specific default if needed
        params['last_checked_time'] = source_data.get('last_checked_time') 

        if not params['name'] or not params['type']:
            self.logger.error("Cannot add news source: 'name' and 'type' are required.")
            return None
        
        # Filter params to only include actual columns defined in 'cols' before insertion
        final_params = {k: v for k, v in params.items() if k in cols}

        sql = f"""
            INSERT INTO news_sources ({', '.join(final_params.keys())})
            VALUES ({', '.join([':' + col for col in final_params.keys()])})
            RETURNING id;
        """

        try:
            self.cursor.execute(sql, final_params)
            inserted_id_row = self.cursor.fetchone()
            self.conn.commit()
            if inserted_id_row:
                self.logger.info(f"News source '{params['name']}' added with ID: {inserted_id_row[0]}.")
                return inserted_id_row[0]
            else:
                self.logger.error(f"Failed to retrieve ID for added news source '{params['name']}'.")
                return None # Should not happen with RETURNING id
        except sqlite3.IntegrityError as ie:
            self.logger.error(f"Failed to add news source '{params['name']}' due to integrity constraint (e.g., unique name violated): {ie}", exc_info=True)
            try: self.conn.rollback() 
            except Exception as re: self.logger.error(f"Rollback failed: {re}", exc_info=True)
            return None
        except sqlite3.Error as e:
            self.logger.error(f"Failed to add news source '{params['name']}': {e}", exc_info=True)
            try: self.conn.rollback()
            except Exception as re: self.logger.error(f"Rollback failed: {re}", exc_info=True)
            return None

    def update_news_source(self, source_id_or_name: Union[int, str], update_data: Dict[str, Any]) -> bool:
        """
        更新指定 ID 或名称的新闻源记录。

        Args:
            source_id_or_name: 要更新的源的 ID (int) 或名称 (str)。通过名称更新时需要注意名称必须唯一。
            update_data: 包含要更新字段及其新值的字典。
                       例如: {'url': 'new_url', 'is_enabled': 0, 'last_checked_time': '...', 'status': 'ok', 'last_error': None, 'consecutive_error_count': 0}

        Returns:
            bool: 更新是否成功。
        """
        if not update_data:
            self.logger.warning("update_news_source called with empty update_data.")
            return False

        # Determine if we are updating by ID or name
        if isinstance(source_id_or_name, int):
            where_clause = "id = ?"
            where_param = (source_id_or_name,)
            log_id = f"ID {source_id_or_name}"
        elif isinstance(source_id_or_name, str):
            where_clause = "name = ?"
            where_param = (source_id_or_name,)
            log_id = f"name '{source_id_or_name}'"
        else:
            self.logger.error(f"Invalid source identifier type: {type(source_id_or_name)}. Must be int (ID) or str (name).")
            return False

        # 检查更新数据是否包含有效字段
        valid_fields = ['name', 'type', 'url', 'category_name', 'is_enabled',
                        'last_checked_time', 'custom_config',
                        'status', 'last_error', 'consecutive_error_count'] # +++ ADDED new fields

        update_pairs = []
        params = []

        for key, value in update_data.items():
            if key in valid_fields:
                update_pairs.append(f"{key} = ?")
                # Convert boolean True/False to 1/0 for is_enabled if needed
                if key == 'is_enabled':
                    params.append(1 if value else 0)
                elif key == 'custom_config' and isinstance(value, dict):
                    # Serialize dict to JSON string for storage
                    try:
                        params.append(json.dumps(value, ensure_ascii=False))
                    except (TypeError, ValueError) as json_e:
                        self.logger.error(f"Failed to serialize custom_config to JSON for source {log_id}: {json_e}")
                        params.append(None) # Store null if serialization fails
                else:
                    # Ensure datetime objects are converted to ISO strings
                    if isinstance(value, datetime):
                         params.append(value.isoformat())
                    else:
                        params.append(value)
            # --- REMOVED 'Skipping unknown field' warnings for status, last_error, consecutive_error_count ---
            # else:
            #    # Only warn if the field is genuinely unexpected now
            #    self.logger.warning(f"Skipping unknown field '{key}' during update for source {log_id}.")

        if not update_pairs:
            self.logger.warning(f"No valid fields found in update_data for source {log_id}. Update cancelled.")
            return False

        sql = f"UPDATE news_sources SET {', '.join(update_pairs)} WHERE {where_clause}"
        params.extend(where_param) # Add the WHERE clause parameter

        try:
            self.lock.acquire() # Acquire lock before DB operation
            self.cursor.execute(sql, params)
            self.conn.commit()
            updated_rows = self.cursor.rowcount
            self.lock.release() # Release lock
            if updated_rows > 0:
                self.logger.info(f"Successfully updated source {log_id}.")
                return True
            else:
                self.logger.warning(f"Source {log_id} not found for update or no changes applied.")
                return False # Source not found or no change
        except sqlite3.Error as e:
            self.logger.error(f"Failed to update news source {log_id}: {e}")
            try: self.conn.rollback() # Attempt rollback
            except sqlite3.Error as rb_e: self.logger.error(f"Rollback failed: {rb_e}")
            if self.lock.locked(): self.lock.release() # Ensure lock is released on error
            return False
        except Exception as e_generic: # Catch other potential errors like JSON serialization issues handled above
             self.logger.error(f"Generic error during update for source {log_id}: {e_generic}", exc_info=True)
             if self.lock.locked(): self.lock.release() # Ensure lock is released on error
             return False

    def delete_news_source(self, source_id: int) -> bool:
        """Deletes a news source from the news_sources table by its ID.

        Args:
            source_id: The ID of the news source to delete.

        Returns:
            True if the deletion was successful (i.e., a row was deleted),
            False otherwise (e.g., source not found or DB error).
        """
        if not self.conn or not self.cursor:
            self.logger.error(f"Database not connected. Cannot delete news source ID {source_id}.")
            return False

        sql = "DELETE FROM news_sources WHERE id = :id;"

        try:
            self.cursor.execute(sql, {'id': source_id})
            self.conn.commit()
            if self.cursor.rowcount > 0:
                self.logger.info(f"News source ID {source_id} deleted successfully.")
                return True
            else:
                self.logger.warning(f"News source ID {source_id} not found for deletion, or no row deleted.")
                return False # Source not found or already deleted
        except sqlite3.Error as e:
            # Foreign key constraints might prevent deletion if articles are linked, 
            # depending on DDL (e.g., ON DELETE RESTRICT).
            # Or other general DB errors.
            self.logger.error(f"Failed to delete news source ID {source_id}: {e}", exc_info=True)
            try: self.conn.rollback()
            except Exception as re: self.logger.error(f"Rollback failed: {re}", exc_info=True)
            return False

    def _news_source_from_row(self, row: sqlite3.Row) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        source_dict = dict(row)
        
        # Deserialize custom_config if it's a JSON string
        if source_dict.get("custom_config") and isinstance(source_dict["custom_config"], str):
            try:
                source_dict["custom_config"] = json.loads(source_dict["custom_config"])
            except json.JSONDecodeError:
                self.logger.warning(f"解析 custom_config JSON 失败 for source ID {source_dict.get('id')}: {source_dict['custom_config']}")
                source_dict["custom_config"] = None # Or an empty dict {}
        
        # Convert last_checked_time string to datetime object
        if source_dict.get("last_checked_time") and isinstance(source_dict["last_checked_time"], str):
            try:
                source_dict["last_checked_time"] = datetime.fromisoformat(source_dict["last_checked_time"].replace('Z', '+00:00'))
            except ValueError:
                self.logger.warning(f"无效的日期时间格式 for 'last_checked_time': {source_dict['last_checked_time']} in source ID {source_dict.get('id')}")
                source_dict["last_checked_time"] = None
                
        # Ensure is_enabled is boolean
        if "is_enabled" in source_dict:
            source_dict["is_enabled"] = bool(source_dict["is_enabled"])
            
        return source_dict

    def _llm_analysis_from_row(self, row: sqlite3.Row) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        
        analysis_dict = dict(row)

        # Convert timestamp string to datetime object
        if analysis_dict.get("analysis_timestamp") and isinstance(analysis_dict["analysis_timestamp"], str):
            try:
                analysis_dict["analysis_timestamp"] = datetime.fromisoformat(analysis_dict["analysis_timestamp"].replace('Z', '+00:00'))
            except ValueError:
                self.logger.warning(f"无效的日期时间格式 for 'analysis_timestamp': {analysis_dict['analysis_timestamp']} in analysis ID {analysis_dict.get('id')}")
                analysis_dict["analysis_timestamp"] = None
        
        # Deserialize JSON string fields
        json_fields = ["meta_news_titles", "meta_news_sources", "meta_categories", "meta_groups", "meta_article_ids", "meta_analysis_params", "meta_error_info"] # Added meta_article_ids and others from DDL
        for field in json_fields:
            if analysis_dict.get(field) and isinstance(analysis_dict[field], str):
                try:
                    analysis_dict[field] = json.loads(analysis_dict[field])
                except json.JSONDecodeError:
                    self.logger.warning(f"解析 JSON 字段 '{field}' 失败 for analysis ID {analysis_dict.get('id')}: {analysis_dict[field]}")
                    analysis_dict[field] = None # Or appropriate default (e.g., [], {})
            # If field is already None or not a string, leave as is.
            # If field might be missing from row, use .get(field)
            
        return analysis_dict

    def add_llm_analysis(self, analysis_data: Dict[str, Any], article_ids_to_map: Optional[List[int]] = None) -> Optional[int]: # Changed article_links to article_ids_to_map
        if not self.conn or not self.cursor:
            self.logger.error("数据库未连接,无法添加LLM分析结果")
            return None

        # Prepare data for llm_analyses table
        # Ensure datetime objects are converted to ISO strings for storage
        analysis_timestamp = analysis_data.get("analysis_timestamp", datetime.now())
        if isinstance(analysis_timestamp, datetime):
            analysis_timestamp_iso = analysis_timestamp.isoformat()
        elif isinstance(analysis_timestamp, str):
            # Assume it's already ISO, or could validate/reformat here
            analysis_timestamp_iso = analysis_timestamp
        else:
            self.logger.warning("Invalid analysis_timestamp type, using current time.")
            analysis_timestamp_iso = datetime.now().isoformat()

        # Serialize metadata fields that are expected to be JSON strings
        meta_fields_to_serialize = ["meta_news_titles", "meta_news_sources", "meta_categories", "meta_groups", "meta_article_ids", "meta_analysis_params", "meta_error_info"]
        
        db_analysis_data = {
            "analysis_timestamp": analysis_timestamp_iso,
            "analysis_type": analysis_data.get("analysis_type", "unknown"),
            "analysis_result_text": analysis_data.get("analysis_result_text"),
            "meta_news_count": analysis_data.get("meta_news_count"), # DDL has this, ensure it's passed or calculated
        }

        for field in meta_fields_to_serialize:
            value = analysis_data.get(field)
            if value is not None:
                try:
                    db_analysis_data[field] = json.dumps(value)
                except TypeError:
                    self.logger.error(f"序列化元数据字段 '{field}' 失败: {value}", exc_info=True)
                    db_analysis_data[field] = None # Or handle error appropriately
            else:
                db_analysis_data[field] = None
        
        # DDL fields: id, analysis_timestamp, analysis_type, analysis_result_text, 
        # meta_news_count, meta_news_titles, meta_news_sources, meta_categories, meta_groups
        # Note: DDL also includes 'meta_prompt_hash' and 'meta_error_info' not explicitly handled here from `analysis_data` keys
        # and 'meta_article_ids' is not in DDL but seems intended. The DDL uses meta_news_count, meta_news_titles etc.
        # The DDL was updated to include `meta_article_ids`, `meta_analysis_params`, `meta_prompt_hash`.
        # This code needs to align with the DDL for llm_analyses table for metadata fields.
        # Let's assume 'analysis_data' contains these pre-serialized or as Python objects.

        fields = ["analysis_timestamp", "analysis_type", "analysis_result_text", 
                  "meta_news_count", "meta_news_titles", "meta_news_sources", 
                  "meta_categories", "meta_groups",
                  "meta_article_ids", "meta_analysis_params", "meta_prompt_hash", "meta_error_info"] # Match DDL + added ones
        
        # Filter analysis_data to only include keys relevant for these fields
        # and ensure values are correctly formatted (esp. JSON strings for text fields)
        final_insert_data = {}
        for field in fields:
            if field in db_analysis_data: # Prioritize already processed/serialized data
                 final_insert_data[field] = db_analysis_data[field]
            else: # Fallback to original analysis_data, may need serialization
                original_value = analysis_data.get(field)
                if field in meta_fields_to_serialize and original_value is not None and not isinstance(original_value, str):
                    try:
                        final_insert_data[field] = json.dumps(original_value)
                    except TypeError:
                        self.logger.error(f"Fallback serialization for '{field}' failed.", exc_info=True)
                        final_insert_data[field] = None
                else:
                    final_insert_data[field] = original_value


        cols = ', '.join(final_insert_data.keys())
        placeholders = ', '.join(['?'] * len(final_insert_data))
        sql = f"INSERT INTO llm_analyses ({cols}) VALUES ({placeholders})"
        
        analysis_id = None
        try:
            with self.conn: # Transaction
                self.cursor.execute(sql, list(final_insert_data.values()))
                analysis_id = self.cursor.lastrowid
                self.logger.info(f"已添加LLM分析结果, ID: {analysis_id}")

                if analysis_id and article_ids_to_map:
                    mappings = []
                    for article_id in article_ids_to_map:
                        if isinstance(article_id, int):
                             mappings.append((article_id, analysis_id))
                        else:
                            self.logger.warning(f"Invalid article_id type in article_ids_to_map: {article_id}")
                    
                    if mappings:
                        self.cursor.executemany(
                            "INSERT OR IGNORE INTO article_analysis_mappings (article_id, analysis_id) VALUES (?, ?)",
                            mappings
                        )
                        self.logger.info(f"为 LLM 分析 ID {analysis_id} 关联了 {len(mappings)} 篇文章。")
            return analysis_id
        except sqlite3.Error as e:
            self.logger.error(f"添加LLM分析结果或关联文章时出错: {e} (Data: {final_insert_data})", exc_info=True)
            return None

    def get_llm_analysis_by_id(self, analysis_id: int) -> Optional[Dict[str, Any]]:
        if not self.conn or not self.cursor: return None
        self.cursor.execute("SELECT * FROM llm_analyses WHERE id = ?", (analysis_id,))
        return self._llm_analysis_from_row(self.cursor.fetchone())

    def get_llm_analyses_for_article(self, article_id: int) -> List[Dict[str, Any]]:
        if not self.conn or not self.cursor: return []
        sql = """
            SELECT la.* FROM llm_analyses la
            JOIN article_analysis_mappings aam ON la.id = aam.analysis_id
            WHERE aam.article_id = :article_id
            ORDER BY la.analysis_timestamp DESC;
        """
        try:
            self.cursor.execute(sql, {'article_id': article_id})
            rows = self.cursor.fetchall()
            return [self._llm_analysis_from_row(row) for row in rows if row]
        except sqlite3.Error as e:
            self.logger.error(f"Error fetching LLM analyses for article ID {article_id}: {e}", exc_info=True)
            return []

    def get_all_llm_analyses(self, limit: Optional[int] = None, offset: Optional[int] = 0) -> List[Dict[str, Any]]:
        if not self.conn or not self.cursor: return []
        query = "SELECT * FROM llm_analyses ORDER BY analysis_timestamp DESC"
        params = {}
        if limit is not None: 
            query += " LIMIT :limit"
            params['limit'] = limit
        if offset != 0: # Offset 0 is default, no need to add clause if 0
            query += " OFFSET :offset"
            params['offset'] = offset
        query += ";"
        try:
            self.cursor.execute(query, params)
            rows = self.cursor.fetchall()
            return [self._llm_analysis_from_row(row) for row in rows if row]
        except sqlite3.Error as e:
            self.logger.error(f"Error fetching all LLM analyses: {e}", exc_info=True)
            return []

    def delete_llm_analysis(self, analysis_id: int) -> bool:
        """Deletes a specific LLM analysis result by its ID.
        Associated mappings in article_analysis_mappings will be deleted by ON DELETE CASCADE.

        Args:
            analysis_id: The ID of the LLM analysis record to delete.

        Returns:
            True if deletion was successful (or record did not exist), False otherwise.
        """
        if not self.conn or not self.cursor:
            self.logger.error("Database not connected. Cannot delete LLM analysis.")
            return False
        
        try:
            with self.conn: # Transaction
                self.cursor.execute("DELETE FROM llm_analyses WHERE id = ?", (analysis_id,))
                if self.cursor.rowcount > 0:
                    self.logger.info(f"LLM analysis record with ID {analysis_id} deleted successfully.")
                else:
                    self.logger.info(f"No LLM analysis record found with ID {analysis_id} to delete.")
                # No need to explicitly delete from article_analysis_mappings due to ON DELETE CASCADE
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Error deleting LLM analysis with ID {analysis_id}: {e}", exc_info=True)
            return False

    def delete_all_llm_analyses(self) -> bool:
        """Deletes all LLM analysis results and their mappings.

        Returns:
            True if deletion was successful, False otherwise.
        """
        if not self.conn or not self.cursor:
            self.logger.error("Database not connected. Cannot delete all LLM analyses.")
            return False
        
        try:
            with self.conn: # Transaction
                # Deleting from llm_analyses will also clear article_analysis_mappings due to CASCADE
                self.cursor.execute("DELETE FROM llm_analyses")
                deleted_count = self.cursor.rowcount
                self.logger.info(f"Successfully deleted {deleted_count} LLM analysis records (and their mappings).")
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Error deleting all LLM analyses: {e}", exc_info=True)
            return False

    def get_latest_history_by_article_id(self, article_id: int) -> Optional[Dict[str, Any]]:
        """获取指定文章ID的最新一条浏览历史记录。"""
        if not self.conn or not self.cursor:
            self.logger.error("数据库未连接，无法获取最新浏览历史")
            return None
        
        sql = """
            SELECT bh.id, bh.view_time 
            FROM browsing_history bh
            WHERE bh.article_id = ?
            ORDER BY bh.view_time DESC
            LIMIT 1;
        """
        try:
            self.cursor.execute(sql, (article_id,))
            row = self.cursor.fetchone()
            if row:
                # Return a simple dict, or process through _history_entry_from_row if needed
                # Use _parse_datetime to convert string back to datetime object
                view_time_dt = None
                view_time_str = row['view_time']
                if view_time_str and isinstance(view_time_str, str):
                    try:
                        view_time_dt = datetime.fromisoformat(view_time_str.replace('Z', '+00:00'))
                    except ValueError:
                        self.logger.warning(f"Invalid datetime format in get_latest_history: {view_time_str}")
                return {'id': row['id'], 'view_time': view_time_dt}
            else:
                return None
        except sqlite3.Error as e:
            self.logger.error(f"获取文章 ID {article_id} 的最新历史记录时出错: {e}", exc_info=True)
            return None

    def delete_articles_with_null_publish_time(self) -> int:
        """Deletes all articles from the 'articles' table where publish_time is NULL.

        Returns:
            int: The number of rows deleted.
        """
        if not self.conn or not self.cursor:
            self.logger.error("Database not connected. Cannot delete articles.")
            return 0

        sql = "DELETE FROM articles WHERE publish_time IS NULL;"
        deleted_rows = 0
        try:
            with self.lock:
                self.logger.info("Attempting to delete articles with NULL publish_time...")
                self.cursor.execute(sql)
                deleted_rows = self.cursor.rowcount
                self.conn.commit()
                self.logger.info(f"Successfully deleted {deleted_rows} articles with NULL publish_time.")
        except sqlite3.Error as e:
            self.logger.error(f"Failed to delete articles with NULL publish_time: {e}", exc_info=True)
            if self.conn: # Check if conn still exists before trying to rollback
                try:
                    self.conn.rollback() # Rollback on error
                    self.logger.info("Rollback successful after failed deletion.")
                except sqlite3.Error as rb_err:
                    self.logger.error(f"Error during rollback: {rb_err}", exc_info=True)
            deleted_rows = -1 # Indicate error
        return deleted_rows