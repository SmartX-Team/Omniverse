class OmniWebGatewayException(Exception):
    """Base exception for Omni Web Gateway"""
    pass


class InvalidMessageFormat(OmniWebGatewayException):
    """Raised when received message format is invalid"""
    pass


class ClientNotRegistered(OmniWebGatewayException):
    """Raised when client tries to send data before registration"""
    pass


class UnsupportedClientType(OmniWebGatewayException):
    """Raised when unsupported client type tries to register"""
    pass
