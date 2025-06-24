#!/usr/bin/env python3
"""Debug script to check roles in database."""

import asyncio

from datasources.queries import RoleQueries
from main import setup_database


async def check_roles():
    session_factory = await setup_database()
    async with session_factory() as session:
        roles = await RoleQueries.get_all_roles(session)
        print("Roles in database:")
        for role in roles:
            print(f"  ID: {role.id}, Name: {role.name}, Type: {role.role_type}")

        # Check specific gender roles
        male_role = await RoleQueries.get_role_by_id(session, 960665311701528599)
        female_role = await RoleQueries.get_role_by_id(session, 960665311701528600)

        print("\nGender roles:")
        print(f"  Male role (960665311701528599): {male_role}")
        print(f"  Female role (960665311701528600): {female_role}")


if __name__ == "__main__":
    asyncio.run(check_roles())
