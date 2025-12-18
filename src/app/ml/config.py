import torch
import os

RUBERT_TINY2_PATH = os.getenv('BASE_MODELS')

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")