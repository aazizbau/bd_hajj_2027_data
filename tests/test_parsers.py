from src.hajj_data.parsers import (
    bengali_number_to_int,
    parse_registration_payload,
    parse_registration_stats,
)


HTML = """
<section class="hajj-registration-info">
  <span id="RegDataGov">৬০৭</span>
  <span id="RegDataPrivate">৮৮৪</span>
  <span id="preRegDataGov">৩,৬০২</span>
  <span id="preRegDataPrivate">৬১,১৬৫</span>
</section>
"""


def test_bengali_number_to_int() -> None:
    assert bengali_number_to_int("৬১,১৬৫") == 61165


def test_parse_registration_stats() -> None:
    stats = parse_registration_stats(HTML)
    assert stats.registered_pligrim_govt == 607
    assert stats.registered_pligrim_nongovt == 884
    assert stats.pre_registered_pilgrim_govt == 3602
    assert stats.pre_registered_pilgrim_nongovt == 61165


def test_parse_registration_payload() -> None:
    payload = {
        "data": {
            "data": {
                "regData": {"Government": "৬০৭", "Private": 884},
                "preragdata": {"Government": "৩,৬০২", "Private": "61165"},
            }
        }
    }
    stats = parse_registration_payload(payload)
    assert stats.registered_pligrim_govt == 607
    assert stats.registered_pligrim_nongovt == 884
    assert stats.pre_registered_pilgrim_govt == 3602
    assert stats.pre_registered_pilgrim_nongovt == 61165
