from enum import StrEnum

class SourceType(StrEnum):
    NEWS_CORPUS = "news_corpus"
    TELEGRAM = "telegram"
    VK = "vk"

class IngestionMode(StrEnum):
    HISTORICAL = "historical"
    INCREMENTAL = "incremental"
    STREAM = "stream"

class JobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    ERROR = "ERROR"

class SentimentLabel(StrEnum):
    NEG = "neg"
    NEU = "neu"
    POS = "pos"

class AccountRole(StrEnum):
    MEMBER = "member"
    VIEWER = "viewer"

class PlanType(StrEnum):
    FREE = "free"
    PREMIUM = "premium"

class SubscriptionStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELED = "canceled"