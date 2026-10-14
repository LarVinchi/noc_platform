import pytest

from app.services.ftth_intake import parse_ftth_request

REQUEST = """FN NUMBER
FN123456
OPEN
CUSTOMER INFORMATION
CUSTOMER NAME
TEST CUSTOMER
SERVICE ADDRESS
1 Test Lane
Oniru, Lagos
SERVICE PACKAGE
100Mbps
CONTACT PHONE
07012345678
EMAIL
orders@example.com
WORK ORDER ID
CO12345678
FN NUMBER
FN123456
SFC ASSIGNED
"""


def test_repeated_fn_and_wrapped_address_are_parsed():
    fields, warnings = parse_ftth_request(REQUEST)
    assert fields == {
        "fn_number": "FN123456", "customer_name": "TEST CUSTOMER",
        "service_address": "1 Test Lane Oniru, Lagos", "bandwidth": "100Mbps",
        "phone_number": "07012345678", "email": "orders@example.com",
        "work_order_id": "CO12345678", "source_status": "OPEN",
    }
    assert len(warnings) == 1 and "New Requests" in warnings[0]


def test_inline_labels_case_and_speed_spacing():
    fields, _ = parse_ftth_request("""fn number: fn123456
customer name: Test Customer
service address: 1 Test Lane
service package: 50 mbps
work order id: co12345678""")
    assert fields["fn_number"] == "FN123456"
    assert fields["work_order_id"] == "CO12345678"
    assert fields["bandwidth"] == "50Mbps"


def test_phone_missing_zero_is_preserved_and_flagged():
    fields, warnings = parse_ftth_request(REQUEST.replace("07012345678", "7012345678"))
    assert fields["phone_number"] == "7012345678"
    assert any("leading zero" in warning for warning in warnings)


@pytest.mark.parametrize("bad_request, message", [
    (REQUEST.replace("FN123456\nSFC", "FN999999\nSFC"), "Conflicting"),
    (REQUEST.replace("CUSTOMER NAME\nTEST CUSTOMER\n", ""), "customer name"),
    (REQUEST.replace("100Mbps", "fast"), "Service package"),
    (REQUEST.replace("100Mbps", "0Mbps"), "positive speed"),
    (REQUEST.replace("07012345678", "phone unavailable"), "Contact phone"),
    ("x" * 20001, "20,000"),
])
def test_invalid_or_combined_requests_are_rejected(bad_request, message):
    with pytest.raises(ValueError, match=message):
        parse_ftth_request(bad_request)
