> Add new optional fields for customer: phone, email

⏺ I'll add phone and email fields to the customer model and form. Let me first check the current database model and then update it accordingly.

⏺ Update Todos
  ⎿  ☐ Examine current customer database model                              
     ☐ Add phone and email fields to database model
     ☐ Update API schemas (CustomerCreate, CustomerUpdate, CustomerResponse)
     ☐ Create database migration for new fields
     ☐ Update frontend form to include phone and email fields
     ☐ Update frontend types

⏺ serena - find_symbol (MCP)(name_path: "Customer", relative_path: "apps/api/app/models/database.py", include_body: true)
  ⎿  [                             
       {
         "name_path": "Customer",
     … +14 lines (ctrl+r to expand)

⏺ Update Todos
  ⎿  ☒ Examine current customer database model                              
     ☐ Add phone and email fields to database model
     ☐ Update API schemas (CustomerCreate, CustomerUpdate, CustomerResponse)
     ☐ Create database migration for new fields
     ☐ Update frontend form to include phone and email fields
     ☐ Update frontend types

⏺ Now I'll add the phone and email fields to the Customer model:

⏺ serena - replace_regex (MCP)(relative_path: "apps/api/app/models/database.py", regex: "    name = Column\\(String\\(255\\)\\)\n    gender =
                              Column\\(String\\(16\\)\\)  # male, female, unknown\n    estimated_age_range = Column\\(String\\(32\\)\\)", repl: "
                              name = Column(String(255))\n    gender = Column(String(16))  # male, female, unknown\n    estimated_age_range =
                              Column(String(32))\n    phone = Column(String(20))\n    email = Column(String(255))")
  ⎿  OK

⏺ Update Todos
  ⎿  ☒ Examine current customer database model                              
     ☒ Add phone and email fields to database model
     ☐ Update API schemas (CustomerCreate, CustomerUpdate, CustomerResponse)
     ☐ Create database migration for new fields
     ☐ Update frontend form to include phone and email fields
     ☐ Update frontend types

⏺ Now I'll update the API schemas to include the new fields:

⏺ serena - find_symbol (MCP)(name_path: "CustomerCreate", relative_path: "apps/api/app/main.py", include_body: true)
  ⎿  [                                 
       {
         "name_path": "CustomerCreate",
     … +10 lines (ctrl+r to expand)

⏺ serena - replace_regex (MCP)(relative_path: "apps/api/app/main.py", regex: "class CustomerCreate\\(BaseModel\\):\n    name: Optional\\[str\\] =
                              None\n    gender: Optional\\[str\\] = None\n    estimated_age_range: Optional\\[str\\] = None", repl: "class
                              CustomerCreate(BaseModel):\n    name: Optional[str] = None\n    gender: Optional[str] = None\n    estimated_age_range:
                              Optional[str] = None\n    phone: Optional[str] = None\n    email: Optional[str] = None")
  ⎿  OK

⏺ serena - find_symbol (MCP)(name_path: "CustomerUpdate", relative_path: "apps/api/app/main.py", include_body: true)
  ⎿  [                                 
       {
         "name_path": "CustomerUpdate",
     … +10 lines (ctrl+r to expand)

⏺ serena - replace_regex (MCP)(relative_path: "apps/api/app/main.py", regex: "class CustomerUpdate\\(BaseModel\\):\n    name: Optional\\[str\\] =
                              None\n    gender: Optional\\[str\\] = None\n    estimated_age_range: Optional\\[str\\] = None", repl: "class
                              CustomerUpdate(BaseModel):\n    name: Optional[str] = None\n    gender: Optional[str] = None\n    estimated_age_range:
                              Optional[str] = None\n    phone: Optional[str] = None\n    email: Optional[str] = None")
  ⎿  OK

⏺ serena - find_symbol (MCP)(name_path: "CustomerResponse", relative_path: "apps/api/app/main.py", include_body: true)
  ⎿  [                                   
       {
         "name_path": "CustomerResponse",
     … +10 lines (ctrl+r to expand)

⏺ serena - replace_regex (MCP)(relative_path: "apps/api/app/main.py", regex: "class CustomerResponse\\(BaseModel\\):\n    tenant_id: str\n
                              customer_id: int\n    name: Optional\\[str\\]\n    gender: Optional\\[str\\]\n    first_seen: datetime\n    last_seen:
                              Optional\\[datetime\\]\n    visit_count: int", repl: "class CustomerResponse(BaseModel):\n    tenant_id: str\n
                              customer_id: int\n    name: Optional[str]\n    gender: Optional[str]\n    estimated_age_range: Optional[str]\n    phone:
                               Optional[str]\n    email: Optional[str]\n    first_seen: datetime\n    last_seen: Optional[datetime]\n    visit_count:
                              int")
  ⎿  OK

⏺ Now I need to update the API endpoint to handle the new fields in customer creation and updates:

⏺ serena - find_symbol (MCP)(name_path: "create_customer", relative_path: "apps/api/app/main.py", include_body: true)
  ⎿  [                                  
       {
         "name_path": "create_customer",
     … +13 lines (ctrl+r to expand)

⏺ serena - replace_regex (MCP)(relative_path: "apps/api/app/main.py", regex: "    new_customer = Customer\\(\n
                              tenant_id=user\\[\"tenant_id\"\\],\n        name=customer\\.name,\n        gender=customer\\.gender,\n
                              estimated_age_range=customer\\.estimated_age_range\n    \\)", repl: "    new_customer = Customer(\n
                              tenant_id=user[\"tenant_id\"],\n        name=customer.name,\n        gender=customer.gender,\n
                              estimated_age_range=customer.estimated_age_range,\n        phone=customer.phone,\n        email=customer.email\n    )")
  ⎿  OK

⏺ Now I need to update the customer update endpoint:

⏺ serena - find_symbol (MCP)(name_path: "update_customer", relative_path: "apps/api/app/main.py", include_body: true)
  ⎿  [                                  
       {
         "name_path": "update_customer",
     … +16 lines (ctrl+r to expand)

⏺ serena - replace_regex (MCP)(relative_path: "apps/api/app/main.py", regex: "    # Update customer fields\n    if customer_update\\.name is not
                              None:\n        customer\\.name = customer_update\\.name\n    if customer_update\\.gender is not None:\n
                              customer\\.gender = customer_update\\.gender\n    if customer_update\\.estimated_age_range is not None:\n
                              customer\\.estimated_age_range = customer_update\\.estimated_age_range", repl: "    # Update customer fields\n    if
                              customer_update.name is not None:\n        customer.name = customer_update.name\n    if customer_update.gender is not
                              None:\n        customer.gender = customer_update.gender\n    if customer_update.estimated_age_range is not None:\n
                                customer.estimated_age_range = customer_update.estimated_age_range\n    if customer_update.phone is not None:\n
                               customer.phone = customer_update.phone\n    if customer_update.email is not None:\n        customer.email =
                              customer_update.email")
  ⎿  OK

⏺ Update Todos
  ⎿  ☒ Examine current customer database model                              
     ☒ Add phone and email fields to database model
     ☒ Update API schemas (CustomerCreate, CustomerUpdate, CustomerResponse)
     ☐ Create database migration for new fields
     ☐ Update frontend form to include phone and email fields
     ☐ Update frontend types


> Progress update by Codex CLI

⏺ Update Todos
  ⎿  ☒ Examine current customer database model
     ☒ Add phone and email fields to database model
     ☒ Update API schemas (CustomerCreate, CustomerUpdate, CustomerResponse)
     ☒ Create database migration for new fields
     ☒ Update frontend form to include phone and email fields
     ☒ Update frontend types

⏺ Changes made
  ⎿  • DB model: added `phone`, `email` to `Customer` in `apps/api/app/models/database.py` (already done by Claude).
     • Alembic: added migration `apps/api/alembic/versions/aa1b2c3d4e5f_add_phone_email_to_customers.py`.
     • SQL migrations: added `apps/api/db/migrations/005_add_customer_contact.sql`.
     • API schemas/handlers: ensured create/update propagate `phone`/`email`.
     • Contracts: updated `contracts/CustomerProfile.v1.json` to include `phone`, `email`.
     • Python shared types: added to `packages/python/common/pkg_common/models.py`.
     • TS shared types: added to `packages/ts/common/src/index.ts`.
     • Web types: extended `apps/web/src/types/api.ts` `Customer` with `estimated_age_range`, `phone`, `email`.
     • Web UI: `Customers` page shows and edits `phone` + `email`.

⏺ Next steps (optional)
  ⎿  • Run API/web unit tests and smoke test create/update customer.
     • If using Alembic in prod, run `alembic upgrade head` or apply SQL 005 in dev DB.
     • Consider adding simple server-side validation for email/phone.
