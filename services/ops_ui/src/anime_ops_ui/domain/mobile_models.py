from pydantic import BaseModel


class HomeFollowingItem(BaseModel):
    appItemId: str
    title: str
    posterUrl: str
    unread: bool
    mappingStatus: str


class SystemOverviewStatusCard(BaseModel):
    title: str
    displayValue: str
    numericValue: float | None = None


class SystemOverviewLineTrend(BaseModel):
    title: str
    displayValue: str
    points: list[float]


class SystemOverviewBarDatum(BaseModel):
    label: str
    value: float
    valueLabel: str


class SystemOverviewBarTrend(BaseModel):
    title: str
    displayValue: str
    bars: list[SystemOverviewBarDatum]


class SystemOverviewSupplementaryItem(BaseModel):
    title: str
    value: str


class SystemDownloadItem(BaseModel):
    id: str
    name: str
    downloadedBytes: int
    totalBytes: int
    progress: float
    downloadSpeedBytesPerSec: int
    stateLabel: str
    state: str
    addedAt: str | None = None


class SystemLogItem(BaseModel):
    id: str
    timestamp: str
    service: str
    level: str
    levelLabel: str
    summary: str
