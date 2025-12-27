import torch
import os

ID2LABEL = {0: "neutral", 1: "positive", 2: "negative"}
BASE_MODEL = os.getenv("RUBERT_BASE_MODEL")
ARTIFACT_DIR = os.getenv("RUBERT_ARTIFACT_DIR")
WEIGHTS_PATH = os.path.join(ARTIFACT_DIR, "model.safetensors")
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")