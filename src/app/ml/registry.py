from typing import Tuple
from transformers import PreTrainedTokenizer, PreTrainedModel

from src.app.ml.model_loader import load_rubert_custom


_tokenizer: PreTrainedTokenizer | None = None
_model: PreTrainedModel | None = None
_id2label: dict[int, str] | None = None


def get_sentiment_model() -> Tuple[
    PreTrainedTokenizer,
    PreTrainedModel,
    dict[int, str],
]:
    """
    Возвращает singleton sentiment model (RuBERT-tiny2).
    Гарантирует, что модель загружена один раз на процесс.
    """

    global _tokenizer, _model, _id2label

    if _tokenizer is None or _model is None:
        _tokenizer, _model, _id2label = load_rubert_custom()

    return _tokenizer, _model, _id2label