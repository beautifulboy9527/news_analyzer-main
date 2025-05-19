# -*- coding: utf-8 -*-
# src/storage/analysis_storage_service.py
import logging
import os
import json
import uuid
from datetime import datetime
from typing import List, Dict, Optional

class AnalysisStorageService:
    """Handles storage and retrieval of LLM analysis results."""

    DEFAULT_SUBDIR = "analysis"
    FILENAME_TEMPLATE = "analysis_{timestamp}_{uuid}.json"

    def __init__(self, data_dir: str):
        """Initialize the service.

        Args:
            data_dir: The base data directory for the application.
        """
        self.logger = logging.getLogger(__name__)
        self.storage_path = os.path.join(data_dir, self.DEFAULT_SUBDIR)
        if not os.path.exists(self.storage_path):
            try:
                os.makedirs(self.storage_path)
                self.logger.info(f"Created analysis storage directory: {self.storage_path}")
            except OSError as e:
                self.logger.error(f"Error creating analysis storage directory {self.storage_path}: {e}", exc_info=True)
                # Depending on strictness, might raise an error here
        self.logger.info(f"AnalysisStorageService initialized. Storage path: {self.storage_path}")

    def save_analysis(self, analysis_data: Dict) -> Optional[str]:
        """Saves a single LLM analysis result to a JSON file.

        Args:
            analysis_data: A dictionary containing the analysis details.
                         Expected keys: 'timestamp' (datetime), 'news_article_title',
                         'news_article_link', 'analysis_type', 'llm_model_used' (optional),
                         'prompt_used' (optional), 'result', 'status', 'error_message' (optional).

        Returns:
            The UUID of the saved analysis if successful, None otherwise.
        """
        if not all(k in analysis_data for k in ['news_article_title', 'news_article_link', 'analysis_type', 'result', 'status']):
            self.logger.error("save_analysis called with missing required keys in analysis_data.")
            return None

        record_uuid = str(uuid.uuid4())
        timestamp_obj = analysis_data.get('timestamp', datetime.now())
        if isinstance(timestamp_obj, datetime):
            timestamp_str = timestamp_obj.strftime("%Y%m%d_%H%M%S")
        elif isinstance(timestamp_obj, str):
            # Try to parse if it's a string, or assume it's already formatted if parsing fails
            try:
                datetime.fromisoformat(timestamp_obj.replace('Z', '+00:00')) # Validate ISO format
                timestamp_str = timestamp_obj # Assume it's an ISO string, use as is for filename part
            except ValueError:
                 # If not ISO, try to use it directly or default
                self.logger.warning(f"Timestamp string '{timestamp_obj}' is not ISO format. Using current time for filename part.")
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        else:
            self.logger.warning(f"Invalid timestamp type: {type(timestamp_obj)}. Using current time for filename part.")
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

        filename = self.FILENAME_TEMPLATE.format(timestamp=timestamp_str, uuid=record_uuid)
        filepath = os.path.join(self.storage_path, filename)

        data_to_save = analysis_data.copy()
        data_to_save['id'] = record_uuid # Ensure 'id' is part of the saved data
        if isinstance(data_to_save.get('timestamp'), datetime):
             data_to_save['timestamp'] = data_to_save['timestamp'].isoformat() # Store timestamp as ISO string

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=4)
            self.logger.info(f"Successfully saved analysis to {filepath} with ID: {record_uuid}")
            return record_uuid
        except IOError as e:
            self.logger.error(f"IOError saving analysis to {filepath}: {e}", exc_info=True)
        except TypeError as e:
            self.logger.error(f"TypeError (JSON serialization) saving analysis to {filepath}: {e}", exc_info=True)
        return None

    def load_all_analyses(self) -> List[Dict]:
        """Loads all analysis records from the storage directory."""
        analyses = []
        if not os.path.exists(self.storage_path):
            self.logger.warning(f"Analysis storage directory {self.storage_path} does not exist. Returning empty list.")
            return analyses
            
        for filename in os.listdir(self.storage_path):
            if filename.startswith("analysis_") and filename.endswith(".json"):
                filepath = os.path.join(self.storage_path, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        analyses.append(data)
                except json.JSONDecodeError as e:
                    self.logger.error(f"Error decoding JSON from {filepath}: {e}", exc_info=True)
                except IOError as e:
                    self.logger.error(f"IOError reading analysis file {filepath}: {e}", exc_info=True)
        
        # Sort by timestamp descending (most recent first)
        try:
            analyses.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        except Exception as e:
            self.logger.error(f"Error sorting analyses: {e}. Returning unsorted.", exc_info=True)
            
        self.logger.debug(f"Loaded {len(analyses)} analysis records.")
        return analyses

    def load_analysis_by_id(self, analysis_id: str) -> Optional[Dict]:
        """Loads a specific analysis record by its UUID.
        
        Note: This is inefficient as it lists all files. 
              For frequent by-ID lookups, a database or an index file would be better.
        """
        if not os.path.exists(self.storage_path):
            return None
            
        for filename in os.listdir(self.storage_path):
            if analysis_id in filename and filename.endswith(".json"):
                filepath = os.path.join(self.storage_path, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if data.get('id') == analysis_id:
                            return data
                except Exception as e:
                    self.logger.error(f"Error loading analysis file {filepath} for ID {analysis_id}: {e}", exc_info=True)
        self.logger.warning(f"Analysis with ID {analysis_id} not found.")
        return None

    def delete_analysis(self, analysis_id: str) -> bool:
        """Deletes a specific analysis record by its UUID.
        
        Note: Similar inefficiency to load_analysis_by_id.
        """
        if not os.path.exists(self.storage_path):
            return False
            
        file_to_delete = None
        for filename in os.listdir(self.storage_path):
            if analysis_id in filename and filename.endswith(".json"):
                # We need to load it to confirm the ID, as filename might just contain the UUID substring
                filepath_check = os.path.join(self.storage_path, filename)
                try:
                    with open(filepath_check, 'r', encoding='utf-8') as f_check:
                        data_check = json.load(f_check)
                        if data_check.get('id') == analysis_id:
                            file_to_delete = filepath_check
                            break 
                except Exception:
                    continue # Skip files that can't be read or don't match ID
        
        if file_to_delete:
            try:
                os.remove(file_to_delete)
                self.logger.info(f"Successfully deleted analysis file: {file_to_delete} (ID: {analysis_id})")
                return True
            except OSError as e:
                self.logger.error(f"Error deleting analysis file {file_to_delete}: {e}", exc_info=True)
                return False
        else:
            self.logger.warning(f"Analysis file for ID {analysis_id} not found for deletion.")
            return False

    def delete_all_analyses(self) -> bool:
        """Deletes all analysis records from the storage directory."""
        deleted_count = 0
        errors = False
        if not os.path.exists(self.storage_path):
            self.logger.info("Analysis storage directory does not exist. Nothing to delete.")
            return True # No files to delete is a success in this context

        for filename in os.listdir(self.storage_path):
            if filename.startswith("analysis_") and filename.endswith(".json"):
                filepath = os.path.join(self.storage_path, filename)
                try:
                    os.remove(filepath)
                    deleted_count += 1
                except OSError as e:
                    self.logger.error(f"Error deleting analysis file {filepath}: {e}", exc_info=True)
                    errors = True
        
        if errors:
            self.logger.warning(f"Finished deleting all analyses with some errors. Deleted {deleted_count} files.")
            return False
        else:
            self.logger.info(f"Successfully deleted all {deleted_count} analysis files.")
            return True

if __name__ == '__main__':
    # Basic Test/Usage Example
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger()
    
    # Create a dummy data directory for testing
    test_data_dir = "_test_data"
    if not os.path.exists(test_data_dir):
        os.makedirs(test_data_dir)
    
    analysis_storage = AnalysisStorageService(data_dir=test_data_dir)
    
    # --- Test save_analysis ---
    analysis1 = {
        'timestamp': datetime.now(),
        'news_article_title': "Test Article 1",
        'news_article_link': "http://example.com/article1",
        'analysis_type': "summary",
        'llm_model_used': "test-model-v1",
        'result': "This is a summary of test article 1.",
        'status': "success"
    }
    analysis1_id = analysis_storage.save_analysis(analysis1)
    logger.info(f"Saved analysis 1 with ID: {analysis1_id}")

    analysis2 = {
        # 'timestamp': datetime.now(), # Test missing timestamp, will use now()
        'news_article_title': "Test Article 2 - Failed Analysis",
        'news_article_link': "http://example.com/article2",
        'analysis_type': "sentiment",
        'result': None, # Or some error object representation
        'status': "error",
        'error_message': "LLM API call failed with 429 Too Many Requests"
    }
    analysis2_id = analysis_storage.save_analysis(analysis2)
    logger.info(f"Saved analysis 2 with ID: {analysis2_id}")

    analysis3_bad_data = {
        'news_article_link': "http://example.com/article3",
        # Missing title, type, result, status
    }
    analysis3_id = analysis_storage.save_analysis(analysis3_bad_data)
    logger.info(f"Attempted to save bad analysis 3, ID: {analysis3_id} (should be None)")

    # --- Test load_all_analyses ---
    all_loaded_analyses = analysis_storage.load_all_analyses()
    logger.info(f"Loaded {len(all_loaded_analyses)} analyses:")
    for an_item in all_loaded_analyses:
        logger.info(f"  ID: {an_item.get('id')}, Title: {an_item.get('news_article_title')}, Type: {an_item.get('analysis_type')}, Timestamp: {an_item.get('timestamp')}")

    # --- Test load_analysis_by_id ---
    if analysis1_id:
        loaded_analysis1 = analysis_storage.load_analysis_by_id(analysis1_id)
        if loaded_analysis1:
            logger.info(f"Successfully loaded analysis by ID {analysis1_id}: {loaded_analysis1.get('news_article_title')}")
        else:
            logger.error(f"Failed to load analysis by ID {analysis1_id}")
    
    loaded_non_existent = analysis_storage.load_analysis_by_id("non-existent-uuid")
    logger.info(f"Attempted to load non-existent ID, result: {loaded_non_existent}")

    # --- Test delete_analysis ---
    if analysis2_id:
        delete_status = analysis_storage.delete_analysis(analysis2_id)
        logger.info(f"Deletion status for analysis ID {analysis2_id}: {delete_status}")
        # Try loading it again
        reloaded_analysis2 = analysis_storage.load_analysis_by_id(analysis2_id)
        logger.info(f"Attempted to reload deleted analysis ID {analysis2_id}, result: {reloaded_analysis2} (should be None)")

    # --- Test delete_all_analyses ---
    # logger.info("Attempting to delete all analyses...")
    # delete_all_status = analysis_storage.delete_all_analyses()
    # logger.info(f"Delete all analyses status: {delete_all_status}")
    # all_after_delete = analysis_storage.load_all_analyses()
    # logger.info(f"Analyses remaining after delete all: {len(all_after_delete)}")

    # Clean up test directory (optional)
    # import shutil
    # shutil.rmtree(test_data_dir)
    # logger.info(f"Cleaned up test data directory: {test_data_dir}") 