from urllib.parse import parse_qs, urlsplit


def _playable_detail_payload() -> dict:
    return {
        "appItemId": "app_following_ab_42",
        "mappingStatus": "mapped",
        "title": "灵笼 第一季",
        "heroState": "playable_primed",
        "hero": {
            "posterUrl": "https://example.com/poster.jpg",
            "backdropUrl": "https://example.com/backdrop.jpg",
            "latestPlayableEpisodeId": "ep_s2_02",
            "latestPlayableJellyfinEpisodeId": "JF-EP-42-2",
            "primedLabel": "E02",
            "playTarget": "jellyfinWeb",
            "playUrl": "http://100.123.232.73:8096/web/#/details?id=JF-SERIES-42",
        },
        "summary": {
            "freshness": "本周更新",
            "availableEpisodeCount": 2,
            "seasonLabel": "S02",
            "score": "9.3",
            "tags": ["Sci-Fi"],
        },
        "overview": "真实简介",
        "playback": {
            "provider": "jellyfin",
            "seriesId": "JF-SERIES-42",
            "defaultSeasonId": "JF-SEASON-42",
            "defaultEpisodeId": "JF-EP-42-2",
            "appDefaultSeasonId": "season_2",
            "appDefaultEpisodeId": "ep_s2_02",
        },
        "seasons": [
            {
                "id": "season_2",
                "label": "S02",
                "selected": True,
                "jellyfinSeriesId": "JF-SERIES-42",
                "jellyfinSeasonId": "JF-SEASON-42",
            }
        ],
        "episodes": [
            {
                "id": "ep_s2_01",
                "label": "E01",
                "seasonId": "season_2",
                "jellyfinSeriesId": "JF-SERIES-42",
                "jellyfinSeasonId": "JF-SEASON-42",
                "jellyfinEpisodeId": "JF-EP-42-1",
                "focused": False,
                "unread": False,
            },
            {
                "id": "ep_s2_02",
                "label": "E02",
                "seasonId": "season_2",
                "jellyfinSeriesId": "JF-SERIES-42",
                "jellyfinSeasonId": "JF-SEASON-42",
                "jellyfinEpisodeId": "JF-EP-42-2",
                "focused": True,
                "unread": True,
            },
        ],
        "recentSeasonal": [],
    }


def _reporting_request_payload(**overrides) -> dict:
    payload = {
        "sessionId": "play_session_demo",
        "positionTicks": 360000000,
        "jellyfinEpisodeId": "JF-EP-42-1",
        "mediaSourceId": "MS-1",
        "audioTrackId": "audio:1",
        "subtitleTrackId": "subtitle:2",
        "playMethod": "directPlay",
        "isPaused": False,
        "failed": False,
        "completed": False,
    }
    payload.update(overrides)
    return payload


def _playback_info_payload() -> dict:
    return {
        "PlaySessionId": "play_session_demo",
        "MediaSources": [
            {
                "Id": "MS-1",
                "Name": "Main",
                "Container": "mkv",
                "Bitrate": 2770756,
                "SupportsTranscoding": True,
                "SupportsDirectPlay": True,
                "SupportsDirectStream": True,
                "DefaultAudioStreamIndex": 1,
                "MediaStreams": [
                    {
                        "Type": "Video",
                        "Index": 0,
                        "Codec": "hevc",
                        "Width": 1920,
                        "Height": 1080,
                    },
                    {
                        "Type": "Audio",
                        "Index": 1,
                        "DisplayTitle": "Japanese - AAC - Stereo - Default",
                        "Language": "jpn",
                        "Codec": "aac",
                        "ChannelLayout": "stereo",
                        "IsDefault": True,
                    },
                    {
                        "Type": "Subtitle",
                        "Index": 2,
                        "DisplayTitle": "简体中文 - Chinese - Default - ASS",
                        "Language": "zho",
                        "Codec": "ass",
                        "IsDefault": True,
                        "IsExternal": False,
                        "IsTextSubtitleStream": True,
                    },
                ],
            }
        ],
    }


def _hls_playback_info_payload() -> dict:
    return {
        "PlaySessionId": "play_session_hls_demo",
        "MediaSources": [
            {
                "Id": "MS-1",
                "SupportsTranscoding": True,
                "SupportsDirectPlay": False,
                "SupportsDirectStream": False,
                "TranscodingUrl": (
                    "/videos/JF-EP-42-1/master.m3u8"
                    "?DeviceId=nekoya-ios&MediaSourceId=MS-1&AudioStreamIndex=1"
                    "&SubtitleStreamIndex=2&SubtitleMethod=Encode&PlaySessionId=play_session_hls_demo"
                    "&ApiKey=TOKEN-1"
                ),
            }
        ],
    }


def _playback_info_payload_with_mov_text() -> dict:
    payload = _playback_info_payload()
    payload["MediaSources"][0]["Container"] = "mp4"
    payload["MediaSources"][0]["MediaStreams"][2]["Codec"] = "mov_text"
    payload["MediaSources"][0]["MediaStreams"][2]["DisplayTitle"] = "简体中文 - Chinese - Default - MOV_TEXT"
    return payload


def test_mobile_playback_bootstrap_returns_media_sources_and_tracks(client, monkeypatch):
    from anime_ops_ui.services import mobile_playback_service

    monkeypatch.setattr(mobile_playback_service, "build_detail_payload", lambda *args, **kwargs: _playable_detail_payload())
    monkeypatch.setattr(
        mobile_playback_service,
        "authenticate_jellyfin_session",
        lambda: mobile_playback_service.JellyfinSession(user_id="USER-1", access_token="TOKEN-1"),
    )
    monkeypatch.setattr(
        mobile_playback_service,
        "fetch_jellyfin_item_detail",
        lambda user_id, jellyfin_item_id, access_token: {
            "RunTimeTicks": 13821445000,
            "UserData": {"PlaybackPositionTicks": 4200000000},
        },
    )
    monkeypatch.setattr(
        mobile_playback_service,
        "fetch_jellyfin_playback_info",
        lambda user_id, jellyfin_item_id, access_token: _playback_info_payload(),
    )

    response = client.get(
        "/api/mobile/items/app_following_ab_42/playback",
        params={"episodeId": "ep_s2_01"},
        headers={"host": "100.123.232.73:3000"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["target"] == {
        "appItemId": "app_following_ab_42",
        "appSeasonId": "season_2",
        "appEpisodeId": "ep_s2_01",
        "jellyfinSeriesId": "JF-SERIES-42",
        "jellyfinSeasonId": "JF-SEASON-42",
        "jellyfinEpisodeId": "JF-EP-42-1",
        "title": "灵笼 第一季",
        "episodeLabel": "E01",
        "durationTicks": 13821445000,
        "resumeTicks": 4200000000,
    }
    assert payload["transport"] == {
        "provider": "jellyfin",
        "mode": "directJellyfin",
        "authMode": "queryApiKey",
        "baseUrl": "http://100.123.232.73:8096",
    }
    assert payload["defaultMediaSourceId"] == "MS-1"
    assert payload["jellyfinPlaySessionId"] == "play_session_demo"
    assert payload["reporting"]["startUrl"] == "/api/mobile/items/app_following_ab_42/playback/session/start"

    media_source = payload["mediaSources"][0]
    assert media_source["id"] == "MS-1"
    assert media_source["videoCodec"] == "hevc"
    assert media_source["width"] == 1920
    assert media_source["height"] == 1080
    assert media_source["defaultAudioTrackId"] == "audio:1"
    assert media_source["defaultSubtitleTrackId"] == "subtitle:2"
    direct_play = urlsplit(media_source["directPlayUrl"])
    direct_query = parse_qs(direct_play.query)
    assert direct_play.netloc == "100.123.232.73:8096"
    assert direct_play.path == "/Videos/JF-EP-42-1/stream"
    assert direct_query["MediaSourceId"] == ["MS-1"]
    assert direct_query["api_key"] == ["TOKEN-1"]
    hls = urlsplit(media_source["transcodeHlsUrl"])
    hls_query = parse_qs(hls.query)
    assert hls.path == "/Videos/JF-EP-42-1/master.m3u8"
    assert hls_query["MediaSourceId"] == ["MS-1"]
    assert hls_query["api_key"] == ["TOKEN-1"]
    assert media_source["audioTracks"] == [
        {
            "id": "audio:1",
            "languageCode": "jpn",
            "displayName": "Japanese - AAC - Stereo - Default",
            "isDefault": True,
            "codec": "aac",
            "channelLayout": "stereo",
            "streamIndex": 1,
        }
    ]
    assert media_source["subtitleTracks"] == [
        {
            "id": "subtitle:off",
            "languageCode": None,
            "displayName": "Off",
            "isDefault": False,
            "delivery": "none",
            "format": None,
            "streamIndex": None,
        },
        {
            "id": "subtitle:2",
            "languageCode": "zho",
            "displayName": "简体中文 - Chinese - Default - ASS",
            "isDefault": True,
            "delivery": "embedded",
            "format": "ass",
            "streamIndex": 2,
        },
    ]


def test_mobile_playback_session_returns_direct_play_stream_descriptor(client, monkeypatch):
    from anime_ops_ui.services import mobile_playback_service

    monkeypatch.setattr(mobile_playback_service, "build_detail_payload", lambda *args, **kwargs: _playable_detail_payload())
    monkeypatch.setattr(
        mobile_playback_service,
        "authenticate_jellyfin_session",
        lambda: mobile_playback_service.JellyfinSession(user_id="USER-1", access_token="TOKEN-1"),
    )
    monkeypatch.setattr(
        mobile_playback_service,
        "fetch_jellyfin_item_detail",
        lambda user_id, jellyfin_item_id, access_token: {
            "RunTimeTicks": 13821445000,
            "UserData": {"PlaybackPositionTicks": 4200000000},
        },
    )
    monkeypatch.setattr(
        mobile_playback_service,
        "fetch_jellyfin_playback_info",
        lambda user_id, jellyfin_item_id, access_token, playback_request=None: _playback_info_payload(),
    )

    response = client.post(
        "/api/mobile/items/app_following_ab_42/playback/session",
        json={
            "appEpisodeId": "ep_s2_01",
            "preferredDelivery": "directPlay",
        },
        headers={"host": "100.123.232.73:3000"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["sessionId"] == "play_session_demo"
    assert payload["target"]["jellyfinEpisodeId"] == "JF-EP-42-1"
    assert payload["stream"] == {
        "delivery": "directPlay",
        "url": "http://100.123.232.73:8096/Videos/JF-EP-42-1/stream?static=true&MediaSourceId=MS-1&api_key=TOKEN-1",
        "headers": {},
    }
    assert payload["selectedMediaSourceId"] == "MS-1"
    assert payload["selectedAudioTrackId"] == "audio:1"
    assert payload["selectedSubtitleTrackId"] == "subtitle:2"
    assert payload["resumeTicks"] == 4200000000
    assert payload["durationTicks"] == 13821445000
    assert payload["reporting"]["stopUrl"] == "/api/mobile/items/app_following_ab_42/playback/session/stop"


def test_mobile_playback_session_auto_prefers_hls_for_unsupported_subtitle_format(client, monkeypatch):
    from anime_ops_ui.services import mobile_playback_service

    playback_requests: list[dict | None] = []

    monkeypatch.setattr(mobile_playback_service, "build_detail_payload", lambda *args, **kwargs: _playable_detail_payload())
    monkeypatch.setattr(
        mobile_playback_service,
        "authenticate_jellyfin_session",
        lambda: mobile_playback_service.JellyfinSession(user_id="USER-1", access_token="TOKEN-1"),
    )
    monkeypatch.setattr(
        mobile_playback_service,
        "fetch_jellyfin_item_detail",
        lambda user_id, jellyfin_item_id, access_token: {
            "RunTimeTicks": 13821445000,
            "UserData": {"PlaybackPositionTicks": 4200000000},
        },
    )
    monkeypatch.setattr(
        mobile_playback_service,
        "fetch_jellyfin_playback_info",
        lambda user_id, jellyfin_item_id, access_token, playback_request=None: (
            playback_requests.append(playback_request),
            _hls_playback_info_payload() if playback_request else _playback_info_payload(),
        )[1],
    )

    response = client.post(
        "/api/mobile/items/app_following_ab_42/playback/session",
        json={
            "appEpisodeId": "ep_s2_01",
            "preferredDelivery": "auto",
        },
        headers={"host": "100.123.232.73:3000"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert playback_requests[0] is None
    assert playback_requests[1] == {
        "UserId": "USER-1",
        "MediaSourceId": "MS-1",
        "AudioStreamIndex": 1,
        "SubtitleStreamIndex": 2,
        "EnableDirectPlay": False,
        "EnableDirectStream": False,
        "EnableTranscoding": True,
        "AllowVideoStreamCopy": False,
        "AllowAudioStreamCopy": False,
        "AlwaysBurnInSubtitleWhenTranscoding": True,
        "DeviceProfile": mobile_playback_service.ios_hls_device_profile(),
    }
    assert payload["sessionId"] == "play_session_hls_demo"
    assert payload["stream"]["delivery"] == "transcodeHls"
    assert payload["stream"]["url"] == (
        "http://100.123.232.73:8096/videos/JF-EP-42-1/master.m3u8"
        "?DeviceId=nekoya-ios&MediaSourceId=MS-1&AudioStreamIndex=1"
        "&SubtitleStreamIndex=2&SubtitleMethod=Encode&PlaySessionId=play_session_hls_demo"
        "&ApiKey=TOKEN-1"
    )
    assert payload["selectedSubtitleTrackId"] == "subtitle:2"


def test_mobile_playback_session_auto_keeps_direct_play_for_mov_text_subtitle(client, monkeypatch):
    from anime_ops_ui.services import mobile_playback_service

    playback_requests: list[dict | None] = []

    monkeypatch.setattr(mobile_playback_service, "build_detail_payload", lambda *args, **kwargs: _playable_detail_payload())
    monkeypatch.setattr(
        mobile_playback_service,
        "authenticate_jellyfin_session",
        lambda: mobile_playback_service.JellyfinSession(user_id="USER-1", access_token="TOKEN-1"),
    )
    monkeypatch.setattr(
        mobile_playback_service,
        "fetch_jellyfin_item_detail",
        lambda user_id, jellyfin_item_id, access_token: {
            "RunTimeTicks": 13821445000,
            "UserData": {"PlaybackPositionTicks": 4200000000},
        },
    )
    monkeypatch.setattr(
        mobile_playback_service,
        "fetch_jellyfin_playback_info",
        lambda user_id, jellyfin_item_id, access_token, playback_request=None: (
            playback_requests.append(playback_request),
            _playback_info_payload_with_mov_text(),
        )[1],
    )

    response = client.post(
        "/api/mobile/items/app_following_ab_42/playback/session",
        json={
            "appEpisodeId": "ep_s2_01",
            "preferredDelivery": "auto",
        },
        headers={"host": "100.123.232.73:3000"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert playback_requests == [None]
    assert payload["stream"]["delivery"] == "directPlay"
    assert payload["selectedSubtitleTrackId"] == "subtitle:2"


def test_mobile_playback_reporting_endpoints_bridge_resume_events_and_mark_completed_stop(client, monkeypatch):
    from anime_ops_ui.services import mobile_playback_service

    position_updates: list[dict] = []
    marked_played: list[dict] = []

    monkeypatch.setattr(mobile_playback_service, "build_detail_payload", lambda *args, **kwargs: _playable_detail_payload())
    monkeypatch.setattr(
        mobile_playback_service,
        "authenticate_jellyfin_session",
        lambda: mobile_playback_service.JellyfinSession(user_id="USER-1", access_token="TOKEN-1"),
    )
    monkeypatch.setattr(
        mobile_playback_service,
        "post_jellyfin_playback_position",
        lambda item_id, user_id, access_token, position_ticks, **kwargs: position_updates.append(
            {
                "item_id": item_id,
                "user_id": user_id,
                "access_token": access_token,
                "position_ticks": position_ticks,
                **kwargs,
            }
        ),
    )
    monkeypatch.setattr(
        mobile_playback_service,
        "post_jellyfin_mark_played",
        lambda item_id, user_id, access_token: marked_played.append(
            {
                "itemId": item_id,
                "userId": user_id,
                "accessToken": access_token,
            }
        ),
    )

    start = client.post(
        "/api/mobile/items/app_following_ab_42/playback/session/start",
        json=_reporting_request_payload(positionTicks=120000000),
        headers={"host": "100.123.232.73:3000"},
    )
    progress = client.post(
        "/api/mobile/items/app_following_ab_42/playback/session/progress",
        json=_reporting_request_payload(positionTicks=240000000, isPaused=True, playMethod="directStream"),
        headers={"host": "100.123.232.73:3000"},
    )
    stop = client.post(
        "/api/mobile/items/app_following_ab_42/playback/session/stop",
        json=_reporting_request_payload(completed=True),
        headers={"host": "100.123.232.73:3000"},
    )

    assert start.status_code == 200
    assert progress.status_code == 200
    assert stop.status_code == 200
    assert start.json() == {
        "ok": True,
        "appItemId": "app_following_ab_42",
        "phase": "start",
        "sessionId": "play_session_demo",
        "positionTicks": 120000000,
    }
    assert progress.json()["phase"] == "progress"
    assert stop.json()["phase"] == "stop"
    assert position_updates == [
        {
            "item_id": "JF-EP-42-1",
            "user_id": "USER-1",
            "access_token": "TOKEN-1",
            "position_ticks": 120000000,
            "session_id": "play_session_demo",
            "media_source_id": "MS-1",
            "audio_track_id": "audio:1",
            "subtitle_track_id": "subtitle:2",
            "play_method": "directPlay",
            "is_paused": False,
            "failed": False,
        },
        {
            "item_id": "JF-EP-42-1",
            "user_id": "USER-1",
            "access_token": "TOKEN-1",
            "position_ticks": 240000000,
            "session_id": "play_session_demo",
            "media_source_id": "MS-1",
            "audio_track_id": "audio:1",
            "subtitle_track_id": "subtitle:2",
            "play_method": "directStream",
            "is_paused": True,
            "failed": False,
        },
    ]
    assert marked_played == [
        {
            "itemId": "JF-EP-42-1",
            "userId": "USER-1",
            "accessToken": "TOKEN-1",
        }
    ]


def test_post_jellyfin_playback_position_updates_user_item_data(monkeypatch):
    from anime_ops_ui.services import mobile_playback_service

    recorded_request: dict = {}

    class Response:
        status_code = 200

    def fake_post(url, *, headers=None, json=None, timeout=None, params=None):
        recorded_request["url"] = url
        recorded_request["headers"] = headers
        recorded_request["json"] = json
        recorded_request["timeout"] = timeout
        recorded_request["params"] = params
        return Response()

    monkeypatch.setattr(mobile_playback_service, "internal_jellyfin_base_url", lambda: "http://jellyfin:8096")
    monkeypatch.setattr(mobile_playback_service.requests, "post", fake_post)

    mobile_playback_service.post_jellyfin_playback_position(
        item_id="JF-EP-42-1",
        user_id="USER-1",
        access_token="TOKEN-1",
        session_id="play_session_demo",
        position_ticks=240000000,
        media_source_id="MS-1",
        audio_track_id="audio:1",
        subtitle_track_id="subtitle:off",
        play_method="transcodeHls",
        is_paused=True,
        failed=False,
    )

    assert recorded_request["url"] == "http://jellyfin:8096/UserItems/JF-EP-42-1/UserData"
    assert recorded_request["headers"] == {
        "X-Emby-Authorization": 'MediaBrowser Client="NekoYa", Device="NekoYaMobile", DeviceId="nekoya-mobile-playback", Version="1.0.0"',
        "X-Emby-Token": "TOKEN-1",
        "Content-Type": "application/json",
    }
    assert recorded_request["params"] == {"userId": "USER-1"}
    assert recorded_request["json"] == {"PlaybackPositionTicks": 240000000}
