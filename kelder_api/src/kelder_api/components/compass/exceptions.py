
class I2CConnectionFailure(Exception):
    def __init__():
        super().__init__(
            "Connection to the I2C board has failed. Check board status light and wiring."
        )