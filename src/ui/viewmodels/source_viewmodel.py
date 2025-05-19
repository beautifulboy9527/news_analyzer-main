from PySide6.QtCore import QObject, Signal

class SourceViewModel(QObject):
    sources_changed = Signal(list)

    def __init__(self, source_manager=None):
        super().__init__()
        self.source_manager = source_manager

    def add_source(self, source):
        if self.source_manager:
            self.source_manager.add_source(source)
        self.sources_changed.emit(self.get_sources())

    def remove_source(self, source):
        if self.source_manager:
            self.source_manager.remove_source(source)
        self.sources_changed.emit(self.get_sources())

    def update_source(self, old, new):
        if self.source_manager:
            self.source_manager.update_source(old, new)
        self.sources_changed.emit(self.get_sources())

    def get_sources(self):
        if self.source_manager:
            try:
                return self.source_manager.get_sources()
            except Exception:
                return []
        return [] 