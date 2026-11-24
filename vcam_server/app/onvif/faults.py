"""ONVIF SOAP faults (ONVIF Core spec, section 5.11)."""


class OnvifFault(Exception):
    def __init__(self, code: str, subcodes: list[str], reason: str, http_status: int = 400):
        super().__init__(reason)
        self.code = code  # "Sender" | "Receiver"
        self.subcodes = subcodes  # e.g. ["ter:InvalidArgVal", "ter:NoProfile"]
        self.reason = reason
        self.http_status = http_status


def not_authorized(reason: str = "Sender not Authorized") -> OnvifFault:
    return OnvifFault("Sender", ["ter:NotAuthorized"], reason, 400)


def action_not_supported(op: str) -> OnvifFault:
    return OnvifFault("Receiver", ["ter:ActionNotSupported"], f"Optional Action {op} Not Implemented", 400)


def invalid_arg(sub: str, reason: str) -> OnvifFault:
    return OnvifFault("Sender", ["ter:InvalidArgVal", f"ter:{sub}"], reason, 400)


def no_profile(token: str | None) -> OnvifFault:
    return invalid_arg("NoProfile", f"Profile token {token!r} does not exist")


def no_config(token: str | None) -> OnvifFault:
    return invalid_arg("NoConfig", f"Configuration token {token!r} does not exist")


def config_modify(reason: str) -> OnvifFault:
    return invalid_arg("ConfigModify", reason)


def action_failed(sub: str, reason: str) -> OnvifFault:
    return OnvifFault("Receiver", ["ter:Action", f"ter:{sub}"], reason, 500)


def well_formed(reason: str = "XML is not well formed") -> OnvifFault:
    return OnvifFault("Sender", ["ter:WellFormed"], reason, 400)
