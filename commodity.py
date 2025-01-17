# commodity.py
from enum import Enum


class Commodity:
    def __init__(self,
                 id: 'int',
                 name: 'str',
                 type: 'Commodity.Type',
                 price: 'float',
                 scu: 'int',
                 missing: bool,
                 status: 'Commodity.Status'):
        self.id = id
        self.name = name
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

    @classmethod
    def transform_commodity_price(cls, commodity):
        type = Commodity.Type.BUY if float(commodity["price_buy"]) > 0 else Commodity.Type.SELL
        price = float(commodity["price_buy"])
        scu = int(commodity["scu_buy"])
        status = None
        if type == Commodity.Type.SELL:
            price = float(commodity["price_sell"])
            scu = int(commodity["scu_sell"])
            status = Commodity.Status.from_value(int(commodity["status_sell"]))
        else:
            status = Commodity.Status.from_value(int(commodity["status_buy"]))
        return Commodity(int(commodity["id"]), commodity["commodity_name"], type, price, scu, False, status)

    class Type(Enum):
        BUY = 1
        SELL = 2

    class Status(Enum):
        UNKNOWN = 0
        OUT_OF_STOCK = 1
        VERY_LOW = 2
        LOW = 3
        MEDIUM = 4
        HIGH = 5
        VERY_HIGH = 6
        MAXIMUM = 7

        @classmethod
        def get_string(cls, value):
            if value == cls.OUT_OF_STOCK.value:
                return "Out Stock"
            elif value == cls.VERY_LOW.value:
                return "Very Low"
            elif value == cls.LOW.value:
                return "Low"
            elif value == cls.MEDIUM.value:
                return "Medium"
            elif value == cls.HIGH.value:
                return "High"
            elif value == cls.VERY_HIGH.value:
                return "Very High"
            elif value == cls.MAXIMUM.value:
                return "Maximum"
            else:
                return "Unknown"

        @classmethod
        def from_value(cls, value):
            for member in cls:
                if member.value == value:
                    return member
            raise ValueError(f"No Status enum member with value {value}")
