import io
import logging
import re
from typing import Any

import pandas as pd
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.customer import Customer
from app.db.models.customer_list import CustomerList, CustomerListContact

logger = logging.getLogger(__name__)


class CustomerListService:

    REQUIRED_COLUMNS = {
        "full_name",
        "mobile_number",
    }

    def __init__(self, db: AsyncSession, current_user):
        self.db = db
        self.current_user = current_user

    @staticmethod
    def normalize_number(value: Any) -> str:
        if pd.isna(value):
            return ""

        # Handle Excel values such as 9876543210.0
        if isinstance(value, float) and value.is_integer():
            value = int(value)

        return re.sub(r"\D", "", str(value))

    @staticmethod
    def normalize_country_code(value: Any) -> str | None:
        if pd.isna(value) or not str(value).strip():
            return None

        return re.sub(r"\D", "", str(value))

    async def import_contacts(
        self,
        name: str,
        file_name: str,
        file_content: bytes,
        tags: list[str] | None = None,
    ) -> dict:

        # 1. Check duplicate list name
        existing_list = await self.db.execute(
            select(CustomerList).where(
                CustomerList.user_id == self.current_user.id,
                CustomerList.name == name,
            )
        )

        if existing_list.scalar_one_or_none():
            raise ValueError(f"A customer list named '{name}' already exists.")

        # 2. Read file
        try:
            if file_name.lower().endswith(".csv"):
                df = pd.read_csv(
                    io.BytesIO(file_content),
                    dtype=str,
                    keep_default_na=False,
                )
            elif file_name.lower().endswith((".xlsx", ".xls")):
                df = pd.read_excel(
                    io.BytesIO(file_content),
                    dtype=str,
                    keep_default_na=False,
                )
            else:
                raise ValueError("Unsupported file format.")

        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"Unable to read uploaded file: {str(exc)}")

        if df.empty:
            raise ValueError("Uploaded file is empty.")

        # 3. Normalize column names
        df.columns = [
            str(column).strip().lower().replace(" ", "_") for column in df.columns
        ]

        missing_columns = self.REQUIRED_COLUMNS - set(df.columns)

        if missing_columns:
            raise ValueError(
                f"Missing required columns: {', '.join(sorted(missing_columns))}"
            )

        # Optional columns
        for column in ("email", "country_code"):
            if column not in df.columns:
                df[column] = ""

        # 4. Validate rows
        valid_rows = []
        invalid_rows = []
        seen_numbers = set()
        duplicate_rows = 0

        for index, row in df.iterrows():

            row_number = index + 2

            full_name = str(row["full_name"]).strip()
            mobile_number = self.normalize_number(row["mobile_number"])
            country_code = self.normalize_country_code(row["country_code"])

            email = str(row["email"]).strip() or None

            if not full_name:
                invalid_rows.append(
                    {
                        "row": row_number,
                        "reason": "Full name is required.",
                    }
                )
                continue

            if not mobile_number:
                invalid_rows.append(
                    {
                        "row": row_number,
                        "reason": "Mobile number is required.",
                    }
                )
                continue

            if mobile_number in seen_numbers:
                duplicate_rows += 1
                continue

            seen_numbers.add(mobile_number)

            valid_rows.append(
                {
                    "full_name": full_name,
                    "mobile_number": mobile_number,
                    "country_code": country_code,
                    "email": email,
                }
            )

        if not valid_rows:
            raise ValueError("No valid contacts found in the uploaded file.")

        try:
            # 5. Fetch existing customers in one query
            uploaded_numbers = [row["mobile_number"] for row in valid_rows]

            result = await self.db.execute(
                select(Customer).where(
                    Customer.user_id == self.current_user.id,
                    Customer.mobile_number.in_(uploaded_numbers),
                )
            )

            existing_customers = {
                customer.mobile_number: customer for customer in result.scalars().all()
            }

            # 6. Create customer list
            customer_list = CustomerList(
                user_id=self.current_user.id,
                name=name,
                source=CustomerList.SourceChoices.FILE_IMPORT,
                original_file_name=file_name,
                tags=tags,
                status="ACTIVE",
            )

            self.db.add(customer_list)
            await self.db.flush()

            new_customers = 0
            reused_customers = 0
            associations = []

            # 7. Create or reuse customers
            for row in valid_rows:

                mobile_number = row["mobile_number"]
                customer = existing_customers.get(mobile_number)

                if customer:
                    # Option B: Preserve existing customer details
                    reused_customers += 1

                else:
                    customer = Customer(
                        user_id=self.current_user.id,
                        full_name=row["full_name"],
                        email=row["email"],
                        country_code=row["country_code"],
                        mobile_number=mobile_number,
                        status="ACTIVE",
                    )

                    self.db.add(customer)
                    await self.db.flush()

                    existing_customers[mobile_number] = customer
                    new_customers += 1

                associations.append(
                    CustomerListContact(
                        customer_list_id=customer_list.id,
                        customer_id=customer.id,
                    )
                )

            # 8. Create associations
            self.db.add_all(associations)

            # Capture response values before commit
            response_data = {
                "customer_list_id": customer_list.id,
                "name": customer_list.name,
                "source": customer_list.source,
                "original_file_name": customer_list.original_file_name,
                "total_contacts": len(associations),
                "new_customers": new_customers,
                "existing_customers_reused": reused_customers,
                "duplicate_rows_skipped": duplicate_rows,
                "invalid_rows_count": len(invalid_rows),
                "invalid_rows": invalid_rows,
            }

            await self.db.commit()

            return response_data

        except Exception:
            await self.db.rollback()
            raise

    async def create_manual_list(
        self,
        name: str,
        contacts: list[dict],
        tags: list[str] | None = None,
    ) -> dict:

        try:
            # 1. Check duplicate list name
            existing_list = await self.db.execute(
                select(CustomerList).where(
                    CustomerList.user_id == self.current_user.id,
                    CustomerList.name == name,
                )
            )

            if existing_list.scalar_one_or_none():
                raise ValueError(f"A customer list named '{name}' already exists.")

            # 2. Create customer list
            customer_list = CustomerList(
                user_id=self.current_user.id,
                name=name,
                source=CustomerList.SourceChoices.MANUAL,
                original_file_name=None,
                tags=tags,
                status="ACTIVE",
            )

            self.db.add(customer_list)
            await self.db.flush()

            new_customers = 0
            reused_customers = 0
            processed_numbers = set()
            associations = []

            # 3. Process contacts
            for contact in contacts:

                mobile_number = self.normalize_number(contact.get("mobile_number"))

                country_code = self.normalize_country_code(contact.get("country_code"))

                full_name = str(contact.get("full_name", "")).strip()

                email = contact.get("email")

                if not full_name:
                    raise ValueError("Customer name is required.")

                if not mobile_number:
                    raise ValueError(f"Mobile number is required for {full_name}.")

                # Avoid duplicate numbers within this request
                if mobile_number in processed_numbers:
                    raise ValueError(f"Duplicate mobile number found: {mobile_number}.")

                processed_numbers.add(mobile_number)

                # 4. Find existing customer
                result = await self.db.execute(
                    select(Customer).where(
                        Customer.user_id == self.current_user.id,
                        Customer.mobile_number == mobile_number,
                    )
                )

                customer = result.scalar_one_or_none()

                if customer:
                    # Option B: Do not update existing customer
                    reused_customers += 1

                else:
                    customer = Customer(
                        user_id=self.current_user.id,
                        full_name=full_name,
                        email=email,
                        country_code=country_code,
                        mobile_number=mobile_number,
                        status="ACTIVE",
                    )

                    self.db.add(customer)
                    await self.db.flush()

                    new_customers += 1

                associations.append(
                    CustomerListContact(
                        customer_list_id=customer_list.id,
                        customer_id=customer.id,
                    )
                )

            # 5. Create list associations
            self.db.add_all(associations)

            # 6. Commit
            await self.db.commit()

            return {
                "customer_list_id": customer_list.id,
                "name": customer_list.name,
                "source": customer_list.source,
                "total_contacts": len(associations),
                "new_customers": new_customers,
                "existing_customers_reused": reused_customers,
            }

        except Exception:
            await self.db.rollback()
            raise

    async def get_customer_lists(
        self,
        page: int = 1,
        page_size: int = 10,
        search: str | None = None,
        source: str | None = None,
        status: str | None = None,
    ) -> dict:

        # Base filters: only the logged-in user's lists
        filters = [
            CustomerList.user_id == self.current_user.id,
        ]

        if search:
            filters.append(CustomerList.name.ilike(f"%{search.strip()}%"))

        if source:
            filters.append(CustomerList.source == source.upper())

        if status:
            filters.append(CustomerList.status == status.upper())

        # 1. Get total matching list count
        count_result = await self.db.execute(
            select(func.count(CustomerList.id)).where(*filters)
        )

        total_records = count_result.scalar_one()

        # 2. Calculate pagination
        offset = (page - 1) * page_size

        # 3. Fetch lists with contact counts
        result = await self.db.execute(
            select(
                CustomerList,
                func.count(CustomerListContact.id).label("total_contacts"),
            )
            .outerjoin(
                CustomerListContact,
                CustomerListContact.customer_list_id == CustomerList.id,
            )
            .where(*filters)
            .group_by(CustomerList.id)
            .order_by(desc(CustomerList.updated_at))
            .offset(offset)
            .limit(page_size)
        )

        rows = result.all()

        customer_lists = []

        for customer_list, total_contacts in rows:
            customer_lists.append(
                {
                    "id": customer_list.id,
                    "name": customer_list.name,
                    "source": customer_list.source,
                    "original_file_name": customer_list.original_file_name,
                    "tags": customer_list.tags or [],
                    "status": customer_list.status,
                    "total_contacts": total_contacts,
                    "created_at": customer_list.created_at,
                    "updated_at": customer_list.updated_at,
                }
            )

        return {
            "items": customer_lists,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_records": total_records,
                "total_pages": (
                    (total_records + page_size - 1) // page_size if total_records else 0
                ),
            },
        }
