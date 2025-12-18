from typing import Iterable
from src.app.domain.entities.document import Document
from src.app.domain.value_objects import AnalysisScope

def filter_documents(docs: Iterable[Document], scope: AnalysisScope) -> list[Document]:
    allowed = set(scope.source_ids)
    start, end = scope.date_range.start, scope.date_range.end
    return [
        d for d in docs
        if d.source_id in allowed and start <= d.published_at <= end
    ]