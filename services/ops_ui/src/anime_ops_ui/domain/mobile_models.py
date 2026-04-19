from pydantic import BaseModel


class HomeFollowingItem(BaseModel):
    appItemId: str
    title: str
    posterUrl: str
    unread: bool
    mappingStatus: str
    jellyfinSeriesId: str | None = None
    premiereYear: str | None = None
    availabilityState: str | None = None


class CalendarDayItem(BaseModel):
    appItemId: str
    title: str
    posterUrl: str
    unread: bool
    availabilityState: str | None = None


class CalendarDayBucket(BaseModel):
    date: str
    weekdayLabel: str
    dayLabel: str
    items: list[CalendarDayItem]


class RSSListItem(BaseModel):
    rssId: int
    title: str
    connectionState: str
    enabled: bool
    lastCheckedLabel: str | None = None


class RSSPreviewItem(BaseModel):
    title: str
    originalTitle: str | None = None
    posterUrl: str | None = None
    year: str | None = None
    season: str | None = None
    tags: list[str]


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
    state: str
    addedAt: str | None = None


class SystemLogItem(BaseModel):
    id: str
    timestamp: str
    service: str
    level: str
    summary: str


class SystemTailscaleLocalNode(BaseModel):
    name: str
    host: str
    ipv4: str
    online: bool


class SystemTailscalePeer(BaseModel):
    name: str
    host: str
    ipv4: str
    online: bool
