# commodity.py
from enum import Enum


class Commodity:
    def __init__(self,
                 id: 'int',
                 type: 'Commodity.Type',
                 price: 'float',
                 scu: 'int',
                 missing: bool,
                 status: 'Commodity.Status'):
        self.id = id
        self.name = "Unknown Commodity"  # TODO - Get Commodity Name from its ID (this also makes sure the Commodity exists)
        self.type = type
        self.price = price
        self.scu = scu
        self.missing = missing
        self.status = status

    def get_price_property(self):
        if self.type == Commodity.Type.BUY:
            return "price_buy"
        else:
            return "price_sell"

    def get_scu_property(self):
        if self.type == Commodity.Type.BUY:
            return "scu_buy"
        else:
            return "scu_sell"

    def get_status_property(self):
        if self.type == Commodity.Type.BUY:
            return "status_buy"
        else:
            return "status_sell"

    class Type(Enum):
        BUY = 1
        SELL = 2

    class Status(Enum):
        OUT_OF_STOCK = 1
        VERY_LOW = 2
        LOW = 3
        MEDIUM = 4
        HIGH = 5
        VERY_HIGH = 6
        MAXIMUM = 7

        @classmethod
        def get_string(cls, value):
            if value == cls.OUT_OF_STOCK:
                return "Out Stock"
            elif value == cls.VERY_LOW:
                return "Very Low"
            elif value == cls.LOW:
                return "Low"
            elif value == cls.MEDIUM:
                return "Medium"
            elif value == cls.HIGH:
                return "High"
            elif value == cls.VERY_HIGH:
                return "Very High"
            elif value == cls.MAXIMUM:
                return "Maximum"
            else:
                return "Unknown value"

        @classmethod
        def from_value(cls, value):
            for member in cls:
                if member.value == value:
                    return member
            raise ValueError(f"No Status enum member with value {value}")
