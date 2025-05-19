"""
Analysis Service Module

Handles coordination of LLM-based analysis tasks for news articles and events.
"""

import logging
import time
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from PySide6.QtCore import QObject, Signal

# Assuming models and other services are importable
from ..models import NewsArticle # Adjust import based on actual location
from ..llm.llm_service import LLMService
from ..storage.news_storage import NewsStorage
from .event_analyzer import EventAnalyzer # Import EventAnalyzer
# Potentially needed for group analysis:
# from .news_clusterer import NewsClusterer

class AnalysisService(QObject):
    """
    Coordinates LLM analysis tasks.

    Signals:
        analysis_started = Signal(str) # Emits a message indicating analysis start
        single_analysis_completed = Signal(str, dict) # Emits analysis type and results dict for one article
        group_analysis_completed = Signal(str, dict) # Emits analysis type and results dict for a group
        analysis_failed = Signal(str, str) # Emits analysis type and error message
        status_message_updated = Signal(str) # Emits status updates during analysis
    """
    analysis_started = Signal(str)
    single_analysis_completed = Signal(str, dict)
    group_analysis_completed = Signal(str, dict)
    analysis_failed = Signal(str, str)
    status_message_updated = Signal(str)

    def __init__(self, llm_service: LLMService, news_storage: NewsStorage, event_analyzer: EventAnalyzer):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.llm_service = llm_service
        self.news_storage = news_storage
        # self.clusterer = clusterer # If needed
        self.event_analyzer = event_analyzer # Inject EventAnalyzer
        self.logger.info("AnalysisService initialized.")

    def analyze_single_article(self, article: NewsArticle, analysis_type: str, custom_prompt: Optional[str] = None):
        """
        Triggers analysis for a single news article and saves the result.

        Args:
            article: The NewsArticle object to analyze.
            analysis_type: Type of analysis (e.g., 'summary', 'importance', 'stance', 'custom').
            custom_prompt: The custom prompt to use if analysis_type is 'custom'.
        """
        if not article or not article.link:
             self.logger.warning("analyze_single_article called with invalid article or missing link.")
             self.analysis_failed.emit(analysis_type, "无效的文章数据")
             return
             
        self.logger.info(f"Starting single article analysis: Type='{analysis_type}', Article='{article.title[:30]}...'" )
        self.status_message_updated.emit(f"开始分析文章: {article.title[:20]}... ({analysis_type})")
        self.analysis_started.emit(analysis_type)

        try:
            # Call the actual LLMService method
            # Assuming llm_service.analyze_news expects the article object or dict
            # And returns a dictionary containing the analysis result.
            result_data = self.llm_service.analyze_news(
                article=article, # Pass the object
                analysis_type=analysis_type,
                custom_prompt=custom_prompt
            )

            if result_data is None:
                 # Handle case where LLM service returns None explicitly
                 self.logger.error(f"LLMService returned None result for analysis type '{analysis_type}' on article {article.link}")
                 raise ValueError("LLM分析未返回结果。")
                 
            # --- Save the result using NewsStorage --- 
            try:
                article_id = getattr(article, 'id', None)
                if article_id is None:
                    # Try to fetch from DB if not on object, though ideally it should be.
                    # This path might indicate an issue upstream if article object isn't complete.
                    self.logger.warning(f"Article ID not present on article object for link {article.link}. Attempting to fetch from DB.")
                    db_article = self.news_storage.get_article_by_link(article.link)
                    if db_article and 'id' in db_article:
                        article_id = db_article['id']
                    else:
                        self.logger.error(f"Failed to retrieve article ID for link {article.link}. Cannot save analysis.")
                        raise ValueError(f"无法获取文章ID以保存分析结果: {article.link}")

                # Construct analysis_data for NewsStorage
                # Determine primary textual result from result_data
                main_result_text = ""
                if isinstance(result_data, str):
                    main_result_text = result_data
                elif isinstance(result_data, dict):
                    # Try common keys for textual output
                    main_result_text = result_data.get('analysis_text', 
                                        result_data.get('summary', 
                                        result_data.get('result', 
                                        str(result_data)))) # Fallback to string representation of dict
                else:
                    main_result_text = str(result_data) # Fallback

                analysis_payload = {
                    "analysis_timestamp": datetime.now().isoformat(),
                    "analysis_type": analysis_type,
                    "analysis_result_text": main_result_text,
                    # meta_article_ids will be handled by add_llm_analysis from article_ids_to_map
                    "meta_news_titles": json.dumps([getattr(article, 'title', 'N/A')]),
                    "meta_news_sources": json.dumps([getattr(article, 'source_name', 'N/A')]),
                    # Placeholder for params and hash, ideally extract from result_data or llm_service
                    "meta_analysis_params": json.dumps(result_data.get("params", {}) if isinstance(result_data, dict) else {}),
                    "meta_prompt_hash": result_data.get("prompt_hash") if isinstance(result_data, dict) else None,
                    "meta_error_info": result_data.get("error") if isinstance(result_data, dict) else None
                }
                
                analysis_id = self.news_storage.add_llm_analysis(analysis_payload, article_ids_to_map=[article_id])
                
                if analysis_id is not None:
                    self.logger.info(f"Successfully saved analysis (ID: {analysis_id}) for article {article.id} (Link: {article.link}, Type: {analysis_type})")
                else:
                    self.logger.error(f"Failed to save analysis result for article {article.id} (Link: {article.link}) (storage returned None ID).")
                    # Optionally, re-raise or handle this failure more explicitly
                    
            except Exception as save_e:
                 # Log error but continue emitting signal
                 self.logger.error(f"Failed to save analysis result for {article.link}: {save_e}", exc_info=True)
                 self.status_message_updated.emit(f"警告: 分析结果保存失败 ({analysis_type})")
            # --- End Save Result --- 
            
            self.single_analysis_completed.emit(analysis_type, result_data)
            self.status_message_updated.emit(f"文章分析完成: ({analysis_type})")
            self.logger.info(f"Successfully completed single analysis: Type='{analysis_type}'")

        except Exception as e:
            self.logger.error(f"Error during single article analysis (Type: {analysis_type}): {e}", exc_info=True)
            error_msg = f"分析失败 ({analysis_type}): {str(e)}"
            self.analysis_failed.emit(analysis_type, error_msg)
            self.status_message_updated.emit(error_msg)

    def analyze_article_group(self, event: Dict, analysis_type: str, custom_prompt: Optional[str] = None):
        """
        Triggers analysis for a clustered event using EventAnalyzer.

        Args:
            event: Dictionary representing the clustered event (output from NewsClusterer).
            analysis_type: Type of analysis (e.g., 'group_summary', 'common_themes', 'combined_stance').
            custom_prompt: Optional custom prompt.
        """
        if not event:
            self.logger.warning("analyze_article_group called with empty event dictionary.")
            self.analysis_failed.emit(analysis_type, "没有可供分析的事件数据。")
            return

        event_title = event.get("title", "未知事件")
        self.logger.info(f"Starting group/event analysis: Type='{analysis_type}', Event='{event_title[:30]}...'" )
        self.status_message_updated.emit(f"开始分析事件: {event_title[:20]}... ({analysis_type})")
        self.analysis_started.emit(analysis_type)

        try:
            # Delegate to EventAnalyzer
            # Determine if using a specific analysis type or custom prompt
            if custom_prompt:
                analysis_result = self.event_analyzer._analyze_with_custom_prompt(event, custom_prompt)
                result_key = 'custom' # Or adjust based on how EventAnalyzer returns custom results
            elif analysis_type == 'importance':
                analysis_result = self.event_analyzer._analyze_importance(event)
                result_key = 'importance'
            elif analysis_type == 'stance':
                analysis_result = self.event_analyzer._analyze_stance(event)
                result_key = 'stance'
            elif analysis_type == 'facts_opinions':
                analysis_result = self.event_analyzer._analyze_facts_opinions(event)
                result_key = 'facts_opinions'
            else:
                # Default to analyzing all aspects if type is generic like 'group' or unknown
                # Or raise an error for unsupported type?
                self.logger.info(f"Unknown or generic analysis type '{analysis_type}'. Performing default analyses.")
                analysis_result = self.event_analyzer.analyze(event)
                result_key = 'all' # Indicate multiple results returned
                
            # Check for errors returned by EventAnalyzer
            if isinstance(analysis_result, dict) and analysis_result.get('error'):
                raise Exception(f"EventAnalyzer failed: {analysis_result['error']}")
            
            # --- Save group analysis results using NewsStorage --- 
            article_ids_for_mapping = []
            titles_for_meta = []
            sources_for_meta = []

            if 'article_ids' in event and isinstance(event['article_ids'], list):
                article_ids_for_mapping = event['article_ids']
                # For titles and sources, we might need to fetch articles if only IDs are present
                # This could be slow. Alternatively, EventAnalyzer's result might include this.
                # For simplicity, let's assume titles/sources might be directly in event or part of analysis_result.
                if 'news_items' in event and isinstance(event['news_items'], list): # If full articles are in event
                    for item_dict in event['news_items']:
                        if isinstance(item_dict, dict):
                            titles_for_meta.append(item_dict.get('title', 'N/A'))
                            sources_for_meta.append(item_dict.get('source_name', 'N/A'))
            elif 'articles' in event and isinstance(event['articles'], list): # If NewsArticle objects are in event
                for article_obj in event['articles']:
                    if hasattr(article_obj, 'id') and article_obj.id is not None:
                        article_ids_for_mapping.append(article_obj.id)
                    if hasattr(article_obj, 'title'):
                        titles_for_meta.append(article_obj.title)
                    if hasattr(article_obj, 'source_name'):
                        sources_for_meta.append(article_obj.source_name)
            else:
                self.logger.warning(f"Could not determine article IDs from event '{event_title}' for saving analysis.")

            if not article_ids_for_mapping:
                 self.logger.warning(f"No article IDs found for event '{event_title}'. Group analysis will not be explicitly mapped to articles in DB.")
            
            # Construct analysis_payload
            main_group_result_text = ""
            if isinstance(analysis_result, str):
                main_group_result_text = analysis_result
            elif isinstance(analysis_result, dict):
                main_group_result_text = analysis_result.get('analysis_text', 
                                           analysis_result.get('summary', 
                                           analysis_result.get('result', 
                                           str(analysis_result))))
            else:
                main_group_result_text = str(analysis_result)

            group_analysis_payload = {
                "analysis_timestamp": datetime.now().isoformat(),
                "analysis_type": analysis_type, # This is the group analysis type
                "analysis_result_text": main_group_result_text,
                "meta_news_titles": json.dumps(titles_for_meta) if titles_for_meta else None,
                "meta_news_sources": json.dumps(sources_for_meta) if sources_for_meta else None,
                # Params for group analysis might come from event_analyzer or be passed down
                "meta_analysis_params": json.dumps(analysis_result.get("params", {}) if isinstance(analysis_result, dict) else {}),
                "meta_prompt_hash": analysis_result.get("prompt_hash") if isinstance(analysis_result, dict) else None,
                "meta_error_info": analysis_result.get("error") if isinstance(analysis_result, dict) else None 
            }
            
            try:
                group_analysis_id = self.news_storage.add_llm_analysis(group_analysis_payload, article_ids_to_map=article_ids_for_mapping if article_ids_for_mapping else None)
                if group_analysis_id is not None:
                    self.logger.info(f"Successfully saved group analysis (ID: {group_analysis_id}) for event '{event_title}' (Type: {analysis_type}). Mapped to {len(article_ids_for_mapping)} articles.")
                else:
                    self.logger.error(f"Failed to save group analysis for event '{event_title}'. Storage returned None ID.")
            except Exception as save_group_e:
                self.logger.error(f"Failed to save group analysis result for event '{event_title}': {save_group_e}", exc_info=True)
                self.status_message_updated.emit(f"警告: 事件分析结果保存失败 ({analysis_type})")
            # --- End Save Group Analysis ---    

            # self.storage.save_group_analysis_result(event_id, analysis_type, analysis_result)
            self.logger.info(f"Event analysis completed by EventAnalyzer. Type: '{analysis_type}'")

            # Emit the result. Adjust signal if needed based on result structure.
            self.group_analysis_completed.emit(analysis_type, analysis_result)
            self.status_message_updated.emit(f"事件分析完成: ({analysis_type})")
            self.logger.info(f"Successfully completed group/event analysis: Type='{analysis_type}'")

        except Exception as e:
            self.logger.error(f"Error during group analysis (Type: {analysis_type}): {e}", exc_info=True)
            error_msg = f"组分析失败 ({analysis_type}): {str(e)}"
            self.analysis_failed.emit(analysis_type, error_msg)
            self.status_message_updated.emit(error_msg)

    # TODO: Implement chat handling logic if migrating chat coordination here
    # def handle_chat_message(self, message_history: List[Dict], user_message: str):
    #     self.logger.info("Handling chat message...")
    #     self.status_message_updated.emit("正在思考...")
    #     try:
    #         # response = self.llm_service.chat(message_history + [{"role": "user", "content": user_message}])
    #         # Emit signal with response
    #         # self.chat_response_received.emit(response)
    #         # self.status_message_updated.emit("AI 回复已生成")
    #         pass # Placeholder
    #     except Exception as e:
    #         self.logger.error(f"Error during chat handling: {e}", exc_info=True)
    #         error_msg = f"聊天失败: {str(e)}"
    #         # Emit failure signal
    #         # self.chat_failed.emit(error_msg)
    #         self.status_message_updated.emit(error_msg)

    # --- Methods for retrieving and deleting LLM analysis results --- 

    def get_llm_analysis_by_id(self, analysis_id: int) -> dict | None:
        """Retrieves a specific LLM analysis result by its ID via NewsStorage."""
        self.logger.debug(f"AnalysisService: Requesting LLM analysis by ID: {analysis_id}")
        try:
            return self.news_storage.get_llm_analysis_by_id(analysis_id)
        except Exception as e:
            self.logger.error(f"AnalysisService: Error getting LLM analysis by ID {analysis_id}: {e}", exc_info=True)
            return None

    def get_llm_analyses_for_article(self, article_id: int) -> List[Dict[str, Any]]:
        """Retrieves all LLM analysis results for a specific article ID via NewsStorage."""
        self.logger.debug(f"AnalysisService: Requesting LLM analyses for article ID: {article_id}")
        try:
            return self.news_storage.get_llm_analyses_for_article(article_id)
        except Exception as e:
            self.logger.error(f"AnalysisService: Error getting LLM analyses for article ID {article_id}: {e}", exc_info=True)
            return []

    def get_all_llm_analyses(self, limit: Optional[int] = None, offset: Optional[int] = 0) -> List[Dict[str, Any]]:
        """Retrieves all LLM analysis results via NewsStorage, with optional pagination."""
        self.logger.debug(f"AnalysisService: Requesting all LLM analyses (limit={limit}, offset={offset})")
        try:
            return self.news_storage.get_all_llm_analyses(limit=limit, offset=offset)
        except Exception as e:
            self.logger.error(f"AnalysisService: Error getting all LLM analyses: {e}", exc_info=True)
            return []

    def delete_llm_analysis(self, analysis_id: int) -> bool:
        """Deletes a specific LLM analysis result by its ID via NewsStorage."""
        self.logger.info(f"AnalysisService: Requesting deletion of LLM analysis ID: {analysis_id}")
        try:
            success = self.news_storage.delete_llm_analysis(analysis_id)
            if success:
                self.status_message_updated.emit(f"分析记录 ID {analysis_id} 已删除。") # Optional: signal success
            else:
                self.logger.warning(f"AnalysisService: NewsStorage failed to delete LLM analysis ID {analysis_id} (returned False).")
                self.status_message_updated.emit(f"删除分析记录 ID {analysis_id} 失败。")
            return success
        except Exception as e:
            self.logger.error(f"AnalysisService: Error deleting LLM analysis ID {analysis_id}: {e}", exc_info=True)
            self.status_message_updated.emit(f"删除分析记录 ID {analysis_id} 失败。")
            return False

    def delete_all_llm_analyses(self) -> bool:
        """Deletes all LLM analysis results via NewsStorage."""
        self.logger.info("AnalysisService: Requesting deletion of all LLM analysis results.")
        try:
            success = self.news_storage.delete_all_llm_analyses()
            if success:
                self.status_message_updated.emit("所有LLM分析记录已删除。") # Optional: signal success
            else:
                self.logger.warning("AnalysisService: NewsStorage failed to delete all LLM analysis results (returned False).")
                self.status_message_updated.emit("删除所有LLM分析记录失败。")
            return success
        except Exception as e:
            self.logger.error(f"AnalysisService: Exception during deletion of all LLM analyses: {e}")
            self.status_message_updated.emit(f"删除所有LLM分析记录时发生错误: {e}")
            return False

