from agentic_travel.services.guide.service import GuideService


def _service() -> GuideService:
    return GuideService.from_default_dataset()


def test_getting_around_present_for_known_city() -> None:
    note = _service().getting_around("city_dxb")
    assert note is not None and len(note) > 10


def test_getting_around_unknown_city_is_none() -> None:
    assert _service().getting_around("city_none") is None


def test_events_include_year_round_and_month() -> None:
    service = _service()
    # Year-round events (month 0) should surface for any month.
    for month in (1, 6, 12):
        events = service.events_for("city_par", month)
        assert all(e.month in (0, month) for e in events)
