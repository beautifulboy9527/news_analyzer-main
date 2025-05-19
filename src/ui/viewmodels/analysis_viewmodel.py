from PySide6.QtCore import QObject, Signal

class AnalysisViewModel(QObject):
    analysis_completed = Signal(str, dict)
    analysis_failed = Signal(str, str)

    def __init__(self, analysis_service=None):
        super().__init__()
        self.analysis_service = analysis_service
        # 假设 analysis_service 有 analysis_completed/failed 信号
        if analysis_service:
            if hasattr(analysis_service, 'analysis_completed'):
                analysis_service.analysis_completed.connect(self._on_analysis_completed)
            if hasattr(analysis_service, 'analysis_failed'):
                analysis_service.analysis_failed.connect(self._on_analysis_failed)

    def analyze_article(self, article, analysis_type):
        if self.analysis_service:
            self.analysis_service.analyze_single_article(article, analysis_type)

    def _on_analysis_completed(self, analysis_type, result):
        self.analysis_completed.emit(analysis_type, result)

    def _on_analysis_failed(self, analysis_type, error):
        self.analysis_failed.emit(analysis_type, error) 