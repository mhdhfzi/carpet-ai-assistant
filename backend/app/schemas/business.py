from pydantic import BaseModel


class BusinessInfo(BaseModel):
    name: str
    demo: bool  # the portfolio demo (fictional business, public read-only login)
    bookings: bool  # whether the assistant takes bookings, or sends customers to WhatsApp
    orders: bool  # whether the dashboard has the back office (orders, customers)
    brand: str  # the name on receipts and the dashboard header (e.g. a trading name)
    logo: str  # the short mark in the round badge, e.g. "RGL"
    address: str  # public: printed on receipts and the website
