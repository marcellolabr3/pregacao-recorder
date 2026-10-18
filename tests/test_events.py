from app.events import EventBus


def test_publish_and_history():
    bus = EventBus()
    bus.publish("gravacao_iniciada", {"message": "oi"})
    bus.publish("gravacao_finalizada", {"message": "fim"})
    items = bus.history()
    assert [i["kind"] for i in items] == ["gravacao_iniciada", "gravacao_finalizada"]
    assert items[0]["seq"] < items[1]["seq"]


def test_history_since_filter():
    bus = EventBus()
    first = bus.publish("a")
    bus.publish("b")
    assert [i["kind"] for i in bus.history(first["seq"])] == ["b"]


def test_history_is_bounded():
    bus = EventBus(history=5)
    for i in range(50):
        bus.publish("e", {"i": i})
    assert len(bus.history()) == 5
    assert bus.history()[-1]["data"]["i"] == 49


def test_subscriber_receives_events():
    bus = EventBus()
    q = bus.subscribe()
    bus.publish("upload_concluido", {"message": "ok"})
    event = q.get_nowait()
    assert event["kind"] == "upload_concluido"
    bus.unsubscribe(q)
    bus.publish("outro", {})
    assert q.empty()


def test_slow_subscriber_does_not_break_publisher():
    bus = EventBus()
    bus.subscribe()  # nunca le
    for _ in range(500):
        bus.publish("filler")
    assert len(bus.history()) == 64
