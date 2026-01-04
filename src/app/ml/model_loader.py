from safetensors.torch import load_file
from transformers import AutoTokenizer

from src.app.ml.models.rubert_custom import RuBertTiny2CustomHead
from src.app.ml.config import WEIGHTS_PATH, ARTIFACT_DIR, BASE_MODEL, ID2LABEL


def load_rubert_custom(device: str = "cpu"):

    model = RuBertTiny2CustomHead(BASE_MODEL, num_labels=3)

    state = load_file(WEIGHTS_PATH)
    model.load_state_dict(state, strict=True)

    model.to(device)
    model.eval()

    tokenizer = AutoTokenizer.from_pretrained(ARTIFACT_DIR, use_fast=True, local_files_only=True)
    id2label = ID2LABEL
    id2label = {int(k): v for k, v in id2label.items()} if isinstance(next(iter(id2label.keys())), str) else id2label

    return tokenizer, model, id2label