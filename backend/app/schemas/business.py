from pydantic import BaseModel


class BusinessInfo(BaseModel):
    name: str
    demo: bool  # the portfolio demo (fictional business, public read-only login)
    bookings: bool  # whether the assistant takes bookings, or sends customers to WhatsApp
