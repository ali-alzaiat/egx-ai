import asyncio, asyncpg, os
async def main():
    c = await asyncpg.connect(os.environ["DATABASE_URL"])
    n = await c.fetchval("SELECT COUNT(DISTINCT company_id) FROM financial_statement_lines WHERE ext_status IN ('approved','auto_validated')")
    print("companies_with_approved_statements:", n)
    await c.close()
asyncio.run(main())
