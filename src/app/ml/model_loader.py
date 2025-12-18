import os
from safetensors.torch import load_file
from transformers import AutoTokenizer

from src.app.ml.models.rubert_custom import RuBertTiny2CustomHead

BASE_MODEL = os.getenv("RUBERT_BASE_MODEL")
ARTIFACT_DIR = os.getenv("RUBERT_ARTIFACT_DIR")
WEIGHTS_PATH = os.path.join(ARTIFACT_DIR, "model.safetensors")

def load_rubert_custom(device: str = "cpu"):

    model = RuBertTiny2CustomHead(BASE_MODEL, num_labels=3)

    state = load_file(WEIGHTS_PATH)
    model.load_state_dict(state, strict=True)

    model.to(device)
    model.eval()

    tokenizer = AutoTokenizer.from_pretrained(ARTIFACT_DIR, use_fast=True, local_files_only=True)
    id2label = {0: "neutral", 1: "positive", 2: "negative"}
    id2label = {int(k): v for k, v in id2label.items()} if isinstance(next(iter(id2label.keys())), str) else id2label

    return tokenizer, model, id2label