from pydantic import BaseModel


class HomeFollowingItem(BaseModel):
    appItemId: str
    title: str
    posterUrl: str
    unread: bool
    mappingStatus: str

