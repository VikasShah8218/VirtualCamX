import pytest
from lxml import etree

from app.onvif import soap
from app.onvif.faults import OnvifFault, no_profile
from app.onvif.xml import el

REQ = b"""<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" xmlns:a="http://www.w3.org/2005/08/addressing">
<s:Header><a:Action>http://www.onvif.org/ver10/events/wsdl/EventPortType/CreatePullPointSubscriptionRequest</a:Action>
<a:MessageID>urn:uuid:1</a:MessageID></s:Header>
<s:Body><CreatePullPointSubscription xmlns="http://www.onvif.org/ver10/events/wsdl"/></s:Body></s:Envelope>"""


def test_parse_request_and_wsa_reply():
    r = soap.parse_request(REQ)
    assert (r.version, r.op, r.ns) == ("1.2", "CreatePullPointSubscription", "http://www.onvif.org/ver10/events/wsdl")
    h = soap.wsa_header(r)
    assert "CreatePullPointSubscriptionResponse</wsa:Action>" in h and "urn:uuid:1" in h


def test_soap11_detected():
    r = soap.parse_request(b'<e:Envelope xmlns:e="http://schemas.xmlsoap.org/soap/envelope/"><e:Body><x:GetHostname xmlns:x="http://www.onvif.org/ver10/device/wsdl"/></e:Body></e:Envelope>')
    assert r.version == "1.1"


def test_malformed_xml_is_wellformed_fault():
    with pytest.raises(OnvifFault) as exc:
        soap.parse_request(b"<not xml")
    assert exc.value.subcodes == ["ter:WellFormed"]


def test_fault_envelope_is_valid_xml_with_nested_subcodes():
    body = soap.fault_body(no_profile("X"), "1.2")
    root = etree.fromstring(soap.envelope(body, "1.2"))
    values = [v.text for v in root.iter("{http://www.w3.org/2003/05/soap-envelope}Value")]
    assert values == ["SOAP-ENV:Sender", "ter:InvalidArgVal", "ter:NoProfile"]


def test_el_escapes_text_and_formats_values():
    x = el("tt:Name", "a<b & c", flag=True, n=1.0, f=0.25)
    assert x == '<tt:Name flag="true" n="1" f="0.25">a&lt;b &amp; c</tt:Name>'
