# import json
# from openai import OpenAI
# from app.utils.mongo_db import get_collection
# # from app.chatmodel.model import model
# from huggingface_hub import login
# import psycopg
# from psycopg.rows import dict_row

# conn = psycopg.connect(
#     host="localhost",
#     port=5432,
#     dbname="scm_procurement",
#     user="postgres",
#     password="root",
#     row_factory=dict_row
# )

# client = OpenAI(
#     api_key="",
#     base_url="https://openrouter.ai/api/v1"
# )

# collection = get_collection("purchase_orders")

# login(token="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")


# SCHEMA = """
# Collection: purchase_orders

# Top-Level Fields:
# po_number - Purchase Order Number
# status - Current PO Status
# supplier_id - Supplier Identifier
# procurement_specialist_id - Procurement Specialist Identifier
# delivery_date - Expected Delivery Date
# mrp_need_by_date - MRP Required Date

# Nested Object: data

# data.id - Unique Purchase Order Identifier
# data.po_number - Purchase Order Number
# data.source_system - Source ERP/System
# data.status - Current PO Status
# data.supplier_id - Supplier Identifier
# data.supplier_name - Supplier Name
# data.supplier_email - Supplier Email Address
# data.site - Delivery or Manufacturing Site
# data.procurement_specialist_id - Procurement Specialist Identifier
# data.delegated_user_id - Delegated User Identifier
# data.currency - Currency Code
# data.total_value - Total Purchase Order Value
# data.delivery_date - Expected Delivery Date
# data.payment_terms - Payment Terms
# data.mrp_exceptions - MRP Exception Type
# data.created_date - PO Creation Date
# data.revision_changes - Number of Revisions

# data.line_items:
#     line_number - Line Item Number
#     material_code - Material Code
#     description - Material Description
#     quantity - Ordered Quantity
#     unit_price - Unit Price
# """


# def generate_query(question):

#     prompt = f"""
#     You are a PostgreSQL SQL query generation engine.

#     Convert the user's question into a valid PostgreSQL SELECT query.

#     Schema:

#     {SCHEMA}

#     Rules:

#     * Return ONLY a valid PostgreSQL SELECT statement.
#     * Do NOT return explanations.
#     * Do NOT return markdown.
#     * Do NOT return code fences.
#     * Query only tables and columns defined in the schema.
#     * Always add LIMIT 20 unless the user explicitly requests a different limit.
#     * Use ILIKE for partial text searches.
#     * Use = for exact matches.
#     * Use >, >=, <, <= for numeric comparisons.
#     * Preserve PO numbers, supplier names, material codes, and IDs exactly as provided.
#     * If a field is stored inside a JSON/JSONB column, use PostgreSQL JSON operators (->, ->>).
#     * If a value is inside a JSON array, use json_array_elements().
#     * When searching inside line_items, unnest the array using CROSS JOIN LATERAL json_array_elements().
#     * Prefer selecting relevant columns instead of SELECT * when the user asks for specific fields.
#     * If the user asks for a field inside line_items (such as description, material_code, quantity, unit_price), extract it from the JSON array.
#     * If both top-level and nested versions of a field exist, prefer the nested JSON field.

#     Examples:

#     Question:
#     Show PO PO-11237

#     Output:
#     SELECT *
#     FROM purchase_orders
#     WHERE po_number = 'PO-11237'
#     LIMIT 20;

#     Question:
#     Show purchase orders for Supplier 8

#     Output:
#     SELECT *
#     FROM purchase_orders
#     WHERE data->>'supplier_name' = 'Supplier 8'
#     LIMIT 20;

#     Question:
#     Show purchase orders with total value greater than 500000

#     Output:
#     SELECT *
#     FROM purchase_orders
#     WHERE (data->>'total_value')::numeric > 500000
#     LIMIT 20;

#     Question:
#     Show line item descriptions for PO-11163

#     Output:
#     SELECT
#     li->>'description' AS description
#     FROM purchase_orders po
#     CROSS JOIN LATERAL json_array_elements(po.data->'line_items') li
#     WHERE po.po_number = 'PO-11163'
#     LIMIT 20;

#     Question:
#     Show purchase orders containing Industrial Component

#     Output:
#     SELECT DISTINCT po.*
#     FROM purchase_orders po
#     CROSS JOIN LATERAL json_array_elements(po.data->'line_items') li
#     WHERE li->>'description' ILIKE '%Industrial Component%'
#     LIMIT 20;

#     Generate SQL for:

#     {question}
#     """


#     response = client.chat.completions.create(
#         model="openai/gpt-oss-120b:free",
#         messages=[
#             {"role": "user", "content": prompt}
#         ]
#     )

#     query_text = response.choices[0].message.content
#     print("Generated Query Text:", query_text)

#     query_text = query_text.replace("```json", "")
#     query_text = query_text.replace("```", "")
#     query_text = query_text.strip()

#     return query_text.strip()


# def ask_question(question):

#     # mongo_query = generate_query(question)

#     # filter_query = mongo_query.get("filter", {})
#     # projection = mongo_query.get("projection", {})

#     # projection["embedding"] = 0

#     sql_query = generate_query(question)

#     # sql_query = "SELECT * FROM purchase_orders WHERE po_number = 'PO-11163'"  # Placeholder query for testing

#     with conn.cursor() as cur:
#         cur.execute(sql_query)
#         data = cur.fetchall()

    
#     print("data:", data)

#     # data = [dict(row) for row in data]

#     # for doc in data:
#     #     doc.pop("embedding", None)
#     #     if "_id" in doc:
#     #         doc["_id"] = str(doc["_id"])

#     prompt = f"""
#     You are a Procurement Business Analyst.

#     The data provided below is the FINAL result of a database query.
#     Your job is to read the records and answer the user's question.

#     Question:
#     {question}

#     Procurement Records:
#     {data}

#     Instructions:

#     1. Use ONLY the information present in the Procurement Records.
#     2. Treat the records as the source of truth.
#     3. Answer the question directly based on the record values.
#     4. If a calculation is required, perform it internally and provide only the result.
#     5. Do NOT generate code.
#     6. Do NOT generate Python.
#     7. Do NOT generate SQL.
#     8. Do NOT generate MongoDB queries.
#     9. Do NOT generate JSON.
#     10. Do NOT generate functions, scripts, algorithms, or pseudocode.
#     11. Do NOT explain how to find the answer.
#     12. Do NOT describe the steps you would take.
#     13. Do NOT return markdown code blocks.
#     14. Do NOT repeat the input data unless necessary to answer the question.
#     15. If the answer is not available in the provided records, respond exactly with:
#         "The requested information is not available in the provided records."

#     Response Requirements:

#     - Respond in plain English.
#     - Respond as a procurement analyst speaking to a business user.
#     - Provide the final answer only.
#     - Be concise and factual.
#     - Include relevant values such as PO number, supplier, status, delivery date, quantities, or total value when applicable.

#     Answer:
#     """

#     response = client.chat.completions.create(
#         model="openai/gpt-oss-120b:free",
#         messages=[
#             {
#                 "role": "user",
#                 "content": prompt
#             }
#         ]
#     )

#     return {
#         "generated_query": sql_query,
#         "records_found": len(data),
#         "data": data,
#         "answer": response.choices[0].message.content
#     }


