from datetime import datetime, timedelta, timezone

import pytest

from videl.web_music_rooms import (
    ListeningRoomError,
    MAX_MEMBERS,
    MAX_QUEUE,
    normalize_code,
    normalize_members,
    normalize_queue,
    normalize_track,
    playback_position,
    require_host,
    require_member,
    room_expiry,
)


def track(video_id="Abcdef_1234", **extra):
    return {"video_id": video_id, "title": "  Song\nTitle ", **extra}


def test_room_code_is_normalized_and_cannot_use_ambiguous_characters():
    assert normalize_code(" abcd2345 ") == "ABCD2345"
    for value in ("ABCDO345", "ABCDI345", "short", "ABCD2345!"):
        with pytest.raises(ListeningRoomError):
            normalize_code(value)


def test_track_metadata_is_bounded_and_thumbnail_is_derived_not_trusted():
    normalized = normalize_track(track(
        title="  A   title\nfor testing ",
        channel=" Channel " * 40,
        duration="3:45",
        thumbnail="javascript:alert(1)",
        stream_url="https://private.invalid/token",
        provider="typetube",
    ))
    assert normalized["title"] == "A title for testing"
    assert len(normalized["channel"]) <= 120
    assert normalized["thumbnail"] == "https://i.ytimg.com/vi/Abcdef_1234/hqdefault.jpg"
    assert "stream_url" not in normalized
    assert normalized["provider"] == "typetube"


def test_queue_is_bounded_deduplicated_and_rejects_untrusted_tracks():
    tracks = [track(f"id_{number:08d}") for number in range(MAX_QUEUE)]
    assert len(normalize_queue(tracks)) == MAX_QUEUE
    with pytest.raises(ListeningRoomError, match="at most"):
        normalize_queue(tracks + [track("last_id_0001")])
    with pytest.raises(ListeningRoomError, match="only once"):
        normalize_queue([track(), track()])
    with pytest.raises(ListeningRoomError):
        normalize_track(track("bad", title="No id"))
    with pytest.raises(ListeningRoomError):
        normalize_track(track(provider="other"))


def test_member_list_is_bounded_unique_and_contains_only_minimal_identity():
    members = normalize_members([{"user": 10, "name": "  Host  ", "username": "private"}, {"user": 20}])
    assert [member["name"] for member in members] == ["Host", "Listener"]
    assert all(set(member) <= {"user", "name", "member_id"} for member in members)
    assert all("username" not in member for member in members)
    with pytest.raises(ListeningRoomError):
        normalize_members([{"user": 10}, {"user": 10}])
    with pytest.raises(ListeningRoomError):
        normalize_members([{"user": True}])
    with pytest.raises(ListeningRoomError, match="between"):
        normalize_members([{"user": number} for number in range(1, MAX_MEMBERS + 2)])


def test_member_can_read_but_only_host_can_mutate_shared_state():
    room = {"host": 10, "members": [{"user": 10}, {"user": 20}]}
    require_member(room, 20)
    require_host(room, 10)
    with pytest.raises(ListeningRoomError, match="Only the host"):
        require_host(room, 20)
    with pytest.raises(ListeningRoomError, match="not a member"):
        require_member(room, 30)
    assert MAX_MEMBERS == 8


def test_playback_position_uses_server_anchor_and_clamps_to_duration():
    anchor = datetime(2026, 10, 19, tzinfo=timezone.utc)
    now = anchor + timedelta(seconds=15)
    assert playback_position({"position": 10, "duration": 60, "playing": True, "anchored_at": anchor}, now) == 25
    assert playback_position({"position": 58, "duration": 60, "playing": True, "anchored_at": anchor}, now) == 60
    # A future anchor never runs the clock backwards.
    assert playback_position({"position": 10, "duration": 60, "playing": True, "anchored_at": now}, anchor) == 10
    with pytest.raises(ListeningRoomError):
        playback_position({"position": -1, "duration": 20, "anchored_at": anchor}, now)


def test_room_hard_expiry_is_enforced_without_ttl_cleanup():
    created = datetime(2026, 10, 19, tzinfo=timezone.utc)
    assert room_expiry(created, created) == created + timedelta(hours=12)
    with pytest.raises(ListeningRoomError, match="expired"):
        room_expiry(created, created + timedelta(hours=12))
