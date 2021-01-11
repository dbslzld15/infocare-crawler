class InfocareClientError(Exception):
    pass


class InfocareClientResponseError(InfocareClientError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(status_code, message)


class InfocareClientParseError(InfocareClientError):
    pass


class InfocareDataParseError(InfocareClientError):
    pass
