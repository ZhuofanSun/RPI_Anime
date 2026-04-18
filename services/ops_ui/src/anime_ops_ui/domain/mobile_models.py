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
