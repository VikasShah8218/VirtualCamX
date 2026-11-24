SOAP12 = "http://www.w3.org/2003/05/soap-envelope"
SOAP11 = "http://schemas.xmlsoap.org/soap/envelope/"

DEVICE = "http://www.onvif.org/ver10/device/wsdl"
MEDIA = "http://www.onvif.org/ver10/media/wsdl"
MEDIA2 = "http://www.onvif.org/ver20/media/wsdl"
EVENTS = "http://www.onvif.org/ver10/events/wsdl"
IMAGING = "http://www.onvif.org/ver20/imaging/wsdl"
PTZ = "http://www.onvif.org/ver20/ptz/wsdl"
DEVICEIO = "http://www.onvif.org/ver10/deviceIO/wsdl"
SCHEMA = "http://www.onvif.org/ver10/schema"
TOPICS = "http://www.onvif.org/ver10/topics"
ERROR = "http://www.onvif.org/ver10/error"
NETWORK = "http://www.onvif.org/ver10/network/wsdl"

WSNT = "http://docs.oasis-open.org/wsn/b-2"
WSTOP = "http://docs.oasis-open.org/wsn/t-1"
WSRF_BF = "http://docs.oasis-open.org/wsrf/bf-2"
WSA = "http://www.w3.org/2005/08/addressing"
WSSE = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
WSU = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
XSD = "http://www.w3.org/2001/XMLSchema"
XSI = "http://www.w3.org/2001/XMLSchema-instance"

# Discovery (WS-Discovery 2005/04, as used by ONVIF)
WSD = "http://schemas.xmlsoap.org/ws/2005/04/discovery"
WSA_2004 = "http://schemas.xmlsoap.org/ws/2004/08/addressing"

# Prefixes declared on every response envelope
PREFIXES = {
    "tds": DEVICE,
    "trt": MEDIA,
    "tr2": MEDIA2,
    "tev": EVENTS,
    "timg": IMAGING,
    "tptz": PTZ,
    "tmd": DEVICEIO,
    "tt": SCHEMA,
    "tns1": TOPICS,
    "ter": ERROR,
    "wsnt": WSNT,
    "wstop": WSTOP,
    "wsa": WSA,
    "xsd": XSD,
    "xsi": XSI,
}

SERVICE_PATHS = {
    DEVICE: "device_service",
    MEDIA: "media_service",
    MEDIA2: "media2_service",
    EVENTS: "events_service",
    IMAGING: "imaging_service",
    PTZ: "ptz_service",
    DEVICEIO: "deviceio_service",
}

SERVICE_VERSIONS = {
    DEVICE: (2, 60),
    MEDIA: (2, 60),
    MEDIA2: (2, 60),
    EVENTS: (2, 60),
    IMAGING: (2, 60),
    PTZ: (2, 60),
    DEVICEIO: (2, 60),
}
