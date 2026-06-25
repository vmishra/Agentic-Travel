from agentic_travel.services.visa.models import VisaCategory
from agentic_travel.services.visa.service import VisaService


def _service() -> VisaService:
    return VisaService.from_default_dataset()


def test_known_evisa_rule() -> None:
    req = _service().assess("IN", "LK")
    assert req.category is VisaCategory.E_VISA
    assert req.processing_days == 2
    assert req.max_stay_days == 30


def test_domestic_requires_nothing() -> None:
    req = _service().assess("IN", "IN")
    assert req.category is VisaCategory.NOT_REQUIRED_DOMESTIC
    assert req.fee is None


def test_unknown_pair_defaults_to_embassy() -> None:
    req = _service().assess("IN", "ZZ")
    assert req.category is VisaCategory.EMBASSY
    assert "embassy" in req.notes.lower()
