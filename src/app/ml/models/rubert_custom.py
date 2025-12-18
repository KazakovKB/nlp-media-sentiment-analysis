import torch
import torch.nn as nn
from transformers import AutoConfig, AutoModel

class RuBertTiny2CustomHead(nn.Module):
    def __init__(self, base_model_name: str, num_labels: int = 3, dropout: float = 0.2):
        super().__init__()
        self.config = AutoConfig.from_pretrained(base_model_name)
        self.bert = AutoModel.from_pretrained(base_model_name, config=self.config)
        hidden = self.config.hidden_size

        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden * 2, hidden // 2)
        self.act = nn.GELU()
        self.out = nn.Linear(hidden // 2, num_labels)

    def forward(self, input_ids=None, attention_mask=None, **kwargs):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        last_hidden = outputs.last_hidden_state

        cls_emb = last_hidden[:, 0]
        if attention_mask is None:
            mean_emb = last_hidden.mean(dim=1)
        else:
            mask = attention_mask.unsqueeze(-1)
            summed = (last_hidden * mask).sum(1)
            denom = mask.sum(1).clamp(min=1e-9)
            mean_emb = summed / denom

        x = torch.cat([cls_emb, mean_emb], dim=-1)
        x = self.dropout(x)
        x = self.fc(x)
        x = self.act(x)
        x = self.dropout(x)
        logits = self.out(x)
        return {"logits": logits}