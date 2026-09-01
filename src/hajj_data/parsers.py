"""Parse Hajj registration statistics from the e-Hajj homepage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup


_BENGALI_TO_ASCII = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


@dataclass(frozen=True)
class RegistrationStats:
    registered_pligrim_govt: int
    registered_pligrim_nongovt: int
    pre_registered_pilgrim_govt: int
    pre_registered_pilgrim_nongovt: int


def bengali_number_to_int(value: str) -> int:
    normalized = value.translate(_BENGALI_TO_ASCII).replace(",", "").strip()
    if not normalized.isdigit():
        raise ValueError(f"Expected a Bengali or English integer, got {value!r}")
    return int(normalized)


def parse_registration_stats(html: str) -> RegistrationStats:
    soup = BeautifulSoup(html, "html.parser")

    def number(element_id: str) -> int:
        element = soup.select_one(f"section.hajj-registration-info #{element_id}")
        if element is None:
            raise ValueError(f"Required element #{element_id} was not found")
        return bengali_number_to_int(element.get_text(strip=True))

    return RegistrationStats(
        registered_pligrim_govt=number("RegDataGov"),
        registered_pligrim_nongovt=number("RegDataPrivate"),
        pre_registered_pilgrim_govt=number("preRegDataGov"),
        pre_registered_pilgrim_nongovt=number("preRegDataPrivate"),
    )


def parse_registration_payload(payload: dict[str, Any]) -> RegistrationStats:
    """Parse the JSON object returned by the site's getCountData endpoint."""
    try:
        data = payload["data"]["data"]
        registered = data["regData"]
        pre_registered = data["preragdata"]  # Spelling used by the official API.
        return RegistrationStats(
            registered_pligrim_govt=bengali_number_to_int(
                str(registered["Government"])
            ),
            registered_pligrim_nongovt=bengali_number_to_int(
                str(registered["Private"])
            ),
            pre_registered_pilgrim_govt=bengali_number_to_int(
                str(pre_registered["Government"])
            ),
            pre_registered_pilgrim_nongovt=bengali_number_to_int(
                str(pre_registered["Private"])
            ),
        )
    except (KeyError, TypeError) as exc:
        raise ValueError("Unexpected getCountData response structure") from exc
