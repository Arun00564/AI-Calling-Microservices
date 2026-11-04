from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.customer import Customer


class CustomerRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_phone(
        self,
        user_id: int,
        mobile_number: str,
    ) -> Customer | None:

        result = await self.db.execute(
            select(Customer).where(
                Customer.user_id == user_id,
                Customer.mobile_number == mobile_number,
            )
        )

        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: int,
        full_name: str,
        mobile_number: str,
        email: str | None = None,
        country_code: str | None = None,
    ) -> Customer:

        customer = Customer(
            user_id=user_id,
            full_name=full_name,
            mobile_number=mobile_number,
            email=email,
            country_code=country_code,
            status="ACTIVE",
        )

        self.db.add(customer)

        await self.db.flush()

        return customer

    async def update(
        self,
        customer: Customer,
        full_name: str | None = None,
        email: str | None = None,
    ) -> Customer:

        if full_name:
            customer.full_name = full_name

        if email:
            customer.email = email

        await self.db.flush()

        return customer
