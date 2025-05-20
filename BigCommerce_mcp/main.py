from fastmcp import FastMCP
from typing import Any, Optional, Dict
from typing import List
from mcp.types import TextContent
import mysql.connector
import asyncio
mcp = FastMCP("BigCommerceMCP",require_api_key=False)
import httpx
import base64
import sys
import os


global STORE_HASH 
global ACCESS_TOKEN 



async def make_bc_request(method: str, endpoint: str, json_data: Any = None) -> Any:
    
    global STORE_HASH
    global ACCESS_TOKEN
    BASE_URL = f"https://api.bigcommerce.com/stores/{STORE_HASH}/v3/catalog/products"
    HEADERS = {
    "X-Auth-Token": ACCESS_TOKEN,
    "Accept": "application/json",
    "Content-Type": "application/json"
}
    url = f"{BASE_URL}{endpoint}"
    print("Store Hash:", STORE_HASH)
    print("Access Token:", ACCESS_TOKEN)
    print("Making request to:", url)
    print("Headers:", HEADERS)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.request(method, url, headers=HEADERS, json=json_data, timeout=30.0)
            print(response.json())
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"HTTP error: {e.response.status_code} - {e.response.text}")
            return {"error": f"HTTP error: {e.response.status_code} - {e.response.text}"}
        except Exception as e:
            print(f"Error: {str(e)}")
            return {"error": str(e)}

##Store Credentials
@mcp.tool(description="Fetches StoreHash and Access Token for BigCommerce. Get Store ID from the user.")
def get_store_credentials(store_id: int) -> Optional[Dict[str, str]]:
    """
    Fetch store_hash and access_token from app_stores table using store ID
    
    Args:
        store_id: The ID of the store
    Returns:
        Success message or None
    """
    try:
        global STORE_HASH
        global ACCESS_TOKEN
        connection = mysql.connector.connect(
            charset="utf8mb4",
            host=os.environ.get("DB_HOST", "158.220.93.14"),
            port=int(os.environ.get("DB_PORT", 3407)),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASS", "ZasHZLBznK0T"),
            database=os.environ.get("DB_NAME", "shopify_stagingpro_dev")
        )
        
        cursor = connection.cursor(dictionary=True)
        
        query = "SELECT store_hash, access_token FROM app_stores WHERE id = %s"
        cursor.execute(query, (store_id,))
        
        result = cursor.fetchone()
        
        if result:
            
            STORE_HASH = result["store_hash"]
            ACCESS_TOKEN = result["access_token"]
            
            return "Store Initialized Successfully"
        return None
    
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return None
        
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals() and connection.is_connected():
            connection.close()

##########PRODUCTS TOOLS
@mcp.tool(description="Creates a new Product in BigCommerce. Product Name is Required. Other fields are optional.If not Mentioned, default values will be used.")
async def create_product(product_data: dict) -> dict:
    """Create a new product with the given fields.
    Required fields: name, type,weight,price
    Ask User for the required fields if not provided.
    """
    result = await make_bc_request("POST", "", product_data)
    if "data" in result and isinstance(result["data"], dict):
        filtered_response = {
            "id": result["data"].get("id"),
            "name": result["data"].get("name")
        }
        return filtered_response
    return result

@mcp.tool(description="Retrieve a product by its ID.")
async def get_product(product_id: int) -> dict:
    """Retrieve a product by its ID.
    Required fields: product_id
    Ask User for the product_id if not provided.
    """
    result = await make_bc_request("GET", f"/{product_id}")
    return result

@mcp.tool(description="Find a product ID (and variant ID, if applicable) by SKU.")
async def find_product_id_by_sku(sku: str) -> dict:
    """
    Find a product ID (and variant ID, if applicable) by SKU.

    Args:
        sku: The SKU to search for.

    Returns:
        A dict with product_id and, if found, variant_id.
    """
    endpoint = f"?sku={sku}"
    result = await make_bc_request("GET", endpoint)

    if "data" not in result or not result["data"]:
        return {"error": f"No product found with SKU '{sku}'."}

    product = result["data"][0]
    response = {"product_id": product["id"]}

    # If variants exist and match the SKU, include variant_id
    if "variants" in product and product["variants"]:
        for variant in product["variants"]:
            if variant.get("sku", "").lower() == sku.lower():
                response["variant_id"] = variant["id"]
                break

    return response

@mcp.tool(description="Create a product variant with specific options. Product ID and SKU is required.")
async def create_product_variant(product_id: int, variant_data: dict) -> dict:
    """
    Create a variant for a specific product.
    
    Args:
        product_id: The ID of the product to create variant for
        variant_data: Dictionary containing variant details
            Required fields: 
            - sku (string): Variant's SKU
            - option_values (array): Array of option values
            
            Optional fields:
            - price (number): Variant's price
            - weight (number): Variant's weight
            - purchasing_disabled (boolean): Whether variant is disabled
            - inventory_level (integer): Stock level
            
    Returns:
        Dict containing created variant details or error message
    """
    # Modify base URL to include product ID and variants endpoint
    global STORE_HASH
    global ACCESS_TOKEN
    
    BASE_URL = f"https://api.bigcommerce.com/stores/{STORE_HASH}/v3/catalog/products/{product_id}/variants"
    HEADERS = {
        "X-Auth-Token": ACCESS_TOKEN,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # Validate required fields
    if not variant_data.get("sku"):
        return {"error": "SKU is required"}
    if not variant_data.get("option_values"):
        return {"error": "option_values array is required"}
        
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                BASE_URL,
                headers=HEADERS,
                json=variant_data,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            
            # Filter and return relevant data
            if "data" in result and isinstance(result["data"], dict):
                filtered_response = {
                    "variant_id": result["data"].get("id"),
                    "product_id": result["data"].get("product_id"),
                    "sku": result["data"].get("sku"),
                    "price": result["data"].get("price"),
                    "inventory_level": result["data"].get("inventory_level")
                }
                return filtered_response
            
            return result
            
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP error: {e.response.status_code} - {e.response.text}"}
        except Exception as e:
            return {"error": str(e)}

@mcp.tool(description="Create a product variant option (like Color, Size, etc). Product ID is required.")
async def create_variant_option(product_id: int, option_data: dict) -> dict:
    """
    Create a variant option for a specific product.
    
    Args:
        product_id: The ID of the product to create option for
        option_data: Dictionary containing option details
            Required fields:
            - display_name (string): The name of the option shown to customers
            - type (string): Type of option (e.g., radio_buttons, dropdown, etc)
            - option_values (array): Array of possible values for this option
            
            Optional fields:
            - sort_order (integer): The order in which the option is displayed
            - config (object): Configuration object for the option
            
    Returns:
        Dict containing created option details or error message
    Example:
        option_data = {
            "display_name": "Color",
            "type": "radio_buttons",
            "option_values": [
                {
                    "label": "Red",
                    "sort_order": 1
                },
                {
                    "label": "Blue",
                    "sort_order": 2
                }
            ]
        }
    """
    global STORE_HASH
    global ACCESS_TOKEN
    
    BASE_URL = f"https://api.bigcommerce.com/stores/{STORE_HASH}/v3/catalog/products/{product_id}/options"
    HEADERS = {
        "X-Auth-Token": ACCESS_TOKEN,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # Validate required fields
    if not option_data.get("display_name"):
        return {"error": "display_name is required"}
    if not option_data.get("type"):
        return {"error": "type is required"}
    if not option_data.get("option_values"):
        return {"error": "option_values array is required"}
    
    # Validate option type
    valid_types = [
        "radio_buttons", "rectangles", "dropdown", "product_list", 
        "product_list_with_images", "swatch"
    ]
    if option_data["type"] not in valid_types:
        return {
            "error": f"Invalid option type. Must be one of: {', '.join(valid_types)}"
        }
        
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                BASE_URL,
                headers=HEADERS,
                json=option_data,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            
            # Filter and return relevant data
            if "data" in result and isinstance(result["data"], dict):
                filtered_response = {
                    "option_id": result["data"].get("id"),
                    "product_id": result["data"].get("product_id"),
                    "display_name": result["data"].get("display_name"),
                    "type": result["data"].get("type"),
                    "option_values": [
                        {
                            "id": value.get("id"),
                            "label": value.get("label")
                        }
                        for value in result["data"].get("option_values", [])
                    ]
                }
                return filtered_response
            
            return result
            
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP error: {e.response.status_code} - {e.response.text}"}
        except Exception as e:
            return {"error": str(e)}

@mcp.tool(description="Update an existing product by ID with new fields.")
async def update_product(product_id: int, update_fields: dict) -> dict:
    """Update an existing product by ID with new fields.
    Allowed fields: name, type, weight, price,description,availability
    Reject If Any other fields are mentioned
    """
    result = await make_bc_request("PUT", f"/{product_id}", update_fields)
    if "data" in result and isinstance(result["data"], dict):
        filtered_response = {
            "id": result["data"].get("id"),
            "name": result["data"].get("name")
        }
        return filtered_response
    return result


@mcp.tool(description="Get all variant options for a specific product.")
async def get_product_variant_options(product_id: int) -> dict:
    """
    Retrieve all variant options for a specific product.
    
    Args:
        product_id: The ID of the product to get options for
        
    Returns:
        Dict containing list of variant options or error message
        
    Example Response:
        {
            "options": [
                {
                    "option_id": 123,
                    "display_name": "Color",
                    "type": "radio_buttons",
                    "option_values": [
                        {
                            "id": 1,
                            "label": "Red"
                        },
                        {
                            "id": 2,
                            "label": "Blue"
                        }
                    ]
                }
            ]
        }
    """
    global STORE_HASH
    global ACCESS_TOKEN
    
    BASE_URL = f"https://api.bigcommerce.com/stores/{STORE_HASH}/v3/catalog/products/{product_id}/options"
    HEADERS = {
        "X-Auth-Token": ACCESS_TOKEN,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                BASE_URL,
                headers=HEADERS,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            
            # Filter and return relevant data
            if "data" in result and isinstance(result["data"], list):
                filtered_options = [
                    {
                        "option_id": option.get("id"),
                        "display_name": option.get("display_name"),
                        "type": option.get("type"),
                        "sort_order": option.get("sort_order"),
                        "option_values": [
                            {
                                "id": value.get("id"),
                                "label": value.get("label"),
                                "sort_order": value.get("sort_order")
                            }
                            for value in option.get("option_values", [])
                        ]
                    }
                    for option in result["data"]
                ]
                return {
                    "options": filtered_options,
                    "total_count": len(filtered_options)
                }
            
            return {"options": [], "total_count": 0}
            
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP error: {e.response.status_code} - {e.response.text}"}
        except Exception as e:
            return {"error": str(e)}

@mcp.tool(description="Get all variants for a specific product.")
async def get_product_variants(product_id: int) -> dict:
    """
    Retrieve all variants for a specific product.
    
    Args:
        product_id: The ID of the product to get variants for
        
    Returns:
        Dict containing list of variants or error message
        
    Example Response:
        {
            "variants": [
                {
                    "id": 123,
                    "sku": "SHIRT-RED-L",
                    "price": 29.99,
                    "inventory_level": 50,
                    "option_values": [
                        {
                            "option_display_name": "Color",
                            "label": "Red"
                        },
                        {
                            "option_display_name": "Size",
                            "label": "Large"
                        }
                    ]
                }
            ],
            "total_count": 1
        }
    """
    global STORE_HASH
    global ACCESS_TOKEN
    
    BASE_URL = f"https://api.bigcommerce.com/stores/{STORE_HASH}/v3/catalog/products/{product_id}/variants"
    HEADERS = {
        "X-Auth-Token": ACCESS_TOKEN,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                BASE_URL,
                headers=HEADERS,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            
            # Filter and return relevant data
            if "data" in result and isinstance(result["data"], list):
                filtered_variants = [
                    {
                        "id": variant.get("id"),
                        "sku": variant.get("sku"),
                        "price": variant.get("price"),
                        "sale_price": variant.get("sale_price"),
                        "inventory_level": variant.get("inventory_level"),
                        "purchasing_disabled": variant.get("purchasing_disabled"),
                        "option_values": [
                            {
                                "option_display_name": value.get("option_display_name"),
                                "label": value.get("label")
                            }
                            for value in variant.get("option_values", [])
                        ]
                    }
                    for variant in result["data"]
                ]
                return {
                    "variants": filtered_variants,
                    "total_count": len(filtered_variants)
                }
            
            return {"variants": [], "total_count": 0}
            
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP error: {e.response.status_code} - {e.response.text}"}
        except Exception as e:
            return {"error": str(e)}


###COUPON TOOLS#######
@mcp.tool(description="Create a per-item discount coupon in BigCommerce.")
async def create_coupon(coupon_data: dict) -> dict:
    """
    Create a per-item discount coupon.
    
    Args:
        coupon_data: Dictionary containing coupon details
            Required fields:
            - name (string): The name of the coupon
            - code (string): Code that customers will enter to receive the discount
            - type (string): Must be "per_item_discount"
            - amount (number): The amount of the discount (in store's currency)
            
            Optional fields:
            - min_purchase (number): Minimum purchase amount required
            - applies_to (object): "entity": "products", "ids": [023, 223]
                     
            - enabled (boolean): Whether coupon is enabled (default True)
            - max_uses (number): Maximum number of times coupon can be used
            - expires (string): Expiration date in ISO 8601 format
            
    Returns:
        Dict containing created coupon details or error message
        
    Example:
        coupon_data = {
            "name": "10 OFF Each Item",
            "code": "10OFFEACH",
            "type": "per_item_discount",
            "amount": 10.00,
            "min_purchase": 20.00,
            "enabled": True
        }
    """
    global STORE_HASH
    global ACCESS_TOKEN
    
    BASE_URL = f"https://api.bigcommerce.com/stores/{STORE_HASH}/v2/coupons"
    HEADERS = {
        "X-Auth-Token": ACCESS_TOKEN,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # Validate required fields
    if not coupon_data.get("name"):
        return {"error": "name is required"}
    if not coupon_data.get("code"):
        return {"error": "code is required"}
    if not coupon_data.get("amount"):
        return {"error": "amount is required"}
        
    # Force type to be per_item_discount
    coupon_data["type"] = "per_item_discount"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                BASE_URL,
                headers=HEADERS,
                json=coupon_data,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            
            # Filter and return relevant data
            if "data" in result and isinstance(result["data"], dict):
                filtered_response = {
                    "id": result["data"].get("id"),
                    "name": result["data"].get("name"),
                    "code": result["data"].get("code"),
                    "amount": result["data"].get("amount"),
                    "type": result["data"].get("type"),
                    "enabled": result["data"].get("enabled"),
                    "expires": result["data"].get("expires")
                }
                return filtered_response
            
            return result
            
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP error: {e.response.status_code} - {e.response.text}"}
        except Exception as e:
            return {"error": str(e)}




#########ORDERS TOOLS######
@mcp.tool(description="Create a new order in BigCommerce with products and customer details.")
async def create_order(order_data: dict) -> dict:
    """
    Create a new order in BigCommerce.
    
    Args:
        order_data: Dictionary containing order details
            Required fields:
            - products (array): List of products in the order
                - product_id (int): Product ID
                - quantity (int): Quantity ordered
            - billing_address: Customer's billing information
                - first_name (string)
                - last_name (string)
                - street_1 (string)
                - city (string)
                - state (string)
                - zip (string)
                - country (string)
                - email (string)
            
            Optional fields:
            - customer_id (int): Existing customer ID
            - status_id (int): Order status (0=pending, 1=shipped, etc)
            - shipping_addresses (array): Shipping address details
            - payment_method (string): Payment method used
            
    Returns:
        Dict containing created order details or error message
        
    Example:
        order_data = {
            "products": [
                {
                    "product_id": 123,
                    "quantity": 2
                }
            ],
            "billing_address": {
                "first_name": "John",
                "last_name": "Doe",
                "street_1": "123 Main St",
                "city": "Austin",
                "state": "Texas",
                "zip": "78701",
                "country": "United States",
                "email": "john@example.com"
            },
            "status_id": 0
        }
    """
    global STORE_HASH
    global ACCESS_TOKEN
    
    BASE_URL = f"https://api.bigcommerce.com/stores/{STORE_HASH}/v2/orders"
    HEADERS = {
        "X-Auth-Token": ACCESS_TOKEN,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # Validate required fields
    if not order_data.get("products"):
        return {"error": "products array is required"}
    if not order_data.get("billing_address"):
        return {"error": "billing_address is required"}
        
    # Validate billing address required fields
    required_billing_fields = [
        "first_name", "last_name", "street_1", 
        "city", "state", "zip", "country", "email"
    ]
    for field in required_billing_fields:
        if not order_data["billing_address"].get(field):
            return {"error": f"billing_address.{field} is required"}
    
    # If shipping_addresses not provided, use billing address
    if not order_data.get("shipping_addresses"):
        order_data["shipping_addresses"] = [order_data["billing_address"]]
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                BASE_URL,
                headers=HEADERS,
                json=order_data,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            
            # Filter and return relevant data
            filtered_response = {
                "id": result.get("id"),
                "status": result.get("status"),
                "customer": {
                    "first_name": result.get("billing_address", {}).get("first_name"),
                    "last_name": result.get("billing_address", {}).get("last_name"),
                    "email": result.get("billing_address", {}).get("email")
                },
                "total_amount": result.get("total_inc_tax"),
                "items_total": result.get("items_total"),
                "payment_method": result.get("payment_method"),
                "date_created": result.get("date_created")
            }
            return filtered_response
            
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP error: {e.response.status_code} - {e.response.text}"}
        except Exception as e:
            return {"error": str(e)}


@mcp.tool(description="Update an existing order in BigCommerce.")
async def update_order(order_id: int, update_data: dict) -> dict:
    """
    Update an existing order in BigCommerce.
    
    Args:
        order_id: ID of the order to update
        update_data: Dictionary containing fields to update
            Updatable fields:
            - status_id (int): New order status
            - customer_id (int): ID of the customer
            - products (array): Updated product list
            - billing_address (dict): Updated billing info
            - shipping_addresses (array): Updated shipping info
            - staff_notes (string): Internal notes
            - customer_message (string): Message to customer
            - payment_method (string): Payment method used
            
    Returns:
        Dict containing updated order details or error message
        
    Example:
        update_data = {
            "status_id": 2,
            "staff_notes": "Order priority upgraded",
            "customer_message": "Your order has been expedited"
        }
    """
    global STORE_HASH
    global ACCESS_TOKEN
    
    BASE_URL = f"https://api.bigcommerce.com/stores/{STORE_HASH}/v2/orders/{order_id}"
    HEADERS = {
        "X-Auth-Token": ACCESS_TOKEN,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # Validate at least one field is being updated
    if not update_data:
        return {"error": "At least one field must be provided for update"}
    
    # List of allowed fields for update
    allowed_fields = {
        "status_id", "customer_id", "products", "billing_address",
        "shipping_addresses", "staff_notes", "customer_message",
        "payment_method"
    }
    
    # Check for invalid fields
    invalid_fields = set(update_data.keys()) - allowed_fields
    if invalid_fields:
        return {"error": f"Invalid fields provided: {', '.join(invalid_fields)}"}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.put(
                BASE_URL,
                headers=HEADERS,
                json=update_data,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            
            # Filter and return relevant data
            filtered_response = {
                "id": result.get("id"),
                "status": result.get("status"),
                "status_id": result.get("status_id"),
                "customer": {
                    "first_name": result.get("billing_address", {}).get("first_name"),
                    "last_name": result.get("billing_address", {}).get("last_name"),
                    "email": result.get("billing_address", {}).get("email")
                },
                "total_amount": result.get("total_inc_tax"),
                "items_total": result.get("items_total"),
                "staff_notes": result.get("staff_notes"),
                "customer_message": result.get("customer_message"),
                "date_modified": result.get("date_modified")
            }
            return filtered_response
            
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP error: {e.response.status_code} - {e.response.text}"}
        except Exception as e:
            return {"error": str(e)}
        
@mcp.tool(description="Retrieve details for a specific order by its ID.")
async def get_order_details(order_id: int) -> dict:
    """
    Retrieve details for a specific order from BigCommerce.

    Args:
        order_id: The ID of the order to retrieve.

    Returns:
        Dict containing order details or error message.

    Example Response:
        {
            "order": {
                "id": 101,
                "status": "Awaiting Fulfillment",
                "date_created": "2024-05-19T12:34:56+00:00",
                "subtotal_ex_tax": 100.00,
                "total_inc_tax": 110.00,
                "customer_id": 123,
                "billing_address": {
                    "first_name": "John",
                    "last_name": "Doe",
                    "email": "john@example.com",
                    "street_1": "123 Main St",
                    "city": "Austin",
                    "state": "TX",
                    "zip": "73301",
                    "country": "United States"
                },
                "shipping_addresses": [
                    {
                        "first_name": "John",
                        "last_name": "Doe",
                        "street_1": "123 Main St",
                        "city": "Austin",
                        "state": "TX",
                        "zip": "73301",
                        "country": "United States"
                    }
                ],
                "products": [
                    {
                        "product_id": 456,
                        "name": "T-Shirt",
                        "sku": "TSHIRT-RED-L",
                        "quantity": 2,
                        "price_inc_tax": 55.00
                    }
                ]
            }
        }
    """
    global STORE_HASH
    global ACCESS_TOKEN

    BASE_URL = f"https://api.bigcommerce.com/stores/{STORE_HASH}/v2/orders/{order_id}"
    HEADERS = {
        "X-Auth-Token": ACCESS_TOKEN,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                BASE_URL,
                headers=HEADERS,
                timeout=30.0
            )
            response.raise_for_status()
            order_data = response.json()

            # Optionally fetch products for the order
            products_url = f"https://api.bigcommerce.com/stores/{STORE_HASH}/v2/orders/{order_id}/products"
            products_response = await client.get(
                products_url,
                headers=HEADERS,
                timeout=30.0
            )
            products_response.raise_for_status()
            products_data = products_response.json()

            # Optionally fetch shipping addresses for the order
            shipping_url = f"https://api.bigcommerce.com/stores/{STORE_HASH}/v2/orders/{order_id}/shipping_addresses"
            shipping_response = await client.get(
                shipping_url,
                headers=HEADERS,
                timeout=30.0
            )
            shipping_response.raise_for_status()
            shipping_data = shipping_response.json()

            # Filter and return relevant data
            order = {
                "id": order_data.get("id"),
                "status": order_data.get("status"),
                "date_created": order_data.get("date_created"),
                "subtotal_ex_tax": order_data.get("subtotal_ex_tax"),
                "total_inc_tax": order_data.get("total_inc_tax"),
                "customer_id": order_data.get("customer_id"),
                "billing_address": {
                    "first_name": order_data.get("billing_address", {}).get("first_name"),
                    "last_name": order_data.get("billing_address", {}).get("last_name"),
                    "email": order_data.get("billing_address", {}).get("email"),
                    "street_1": order_data.get("billing_address", {}).get("street_1"),
                    "city": order_data.get("billing_address", {}).get("city"),
                    "state": order_data.get("billing_address", {}).get("state"),
                    "zip": order_data.get("billing_address", {}).get("zip"),
                    "country": order_data.get("billing_address", {}).get("country")
                },
                "shipping_addresses": [
                    {
                        "first_name": addr.get("first_name"),
                        "last_name": addr.get("last_name"),
                        "street_1": addr.get("street_1"),
                        "city": addr.get("city"),
                        "state": addr.get("state"),
                        "zip": addr.get("zip"),
                        "country": addr.get("country")
                    }
                    for addr in shipping_data
                ] if isinstance(shipping_data, list) else [],
                "products": [
                    {
                        "product_id": prod.get("product_id"),
                        "name": prod.get("name"),
                        "sku": prod.get("sku"),
                        "quantity": prod.get("quantity"),
                        "price_inc_tax": prod.get("price_inc_tax")
                    }
                    for prod in products_data
                ] if isinstance(products_data, list) else []
            }

            return {"order": order}

        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP error: {e.response.status_code} - {e.response.text}"}
        except Exception as e:
            return {"error": str(e)}
        
@mcp.tool(description="List orders with optional filters like status, date range, and more.")
async def list_orders(
    status: Optional[str] = None,
    min_date_created: Optional[str] = None,
    max_date_created: Optional[str] = None,
    customer_id: Optional[int] = None,
    limit: int = 50,
    page: int = 1
) -> dict:
    """
    List orders from BigCommerce with optional filters.
    
    Args:
        status: Filter orders by status (e.g., 'Awaiting Fulfillment', 'Shipped', etc.)
        min_date_created: ISO8601 start date (e.g., '2025-05-18T00:00:00Z')
        max_date_created: ISO8601 end date (e.g., '2025-05-18T23:59:59Z')
        customer_id: Filter by customer ID (optional)
        limit: Number of orders per page (default: 50)
        page: Page number for pagination (default: 1)

    Returns:
        Dict containing a list of orders and pagination info, or error message.

    Example Response:
        {
            "orders": [
                {
                    "id": 1001,
                    "status": "Awaiting Fulfillment",
                    "date_created": "2025-05-18T12:34:56Z",
                    "customer_id": 123,
                    "total_inc_tax": "99.99"
                },
                ...
            ],
            "total_count": 25,
            "page": 1,
            "limit": 50
        }
    """
    global STORE_HASH
    global ACCESS_TOKEN

    BASE_URL = f"https://api.bigcommerce.com/stores/{STORE_HASH}/v2/orders"
    HEADERS = {
        "X-Auth-Token": ACCESS_TOKEN,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    params = {
        "limit": limit,
        "page": page
    }
    if status:
        params["status"] = status
    if min_date_created:
        params["min_date_created"] = min_date_created
    if max_date_created:
        params["max_date_created"] = max_date_created
    if customer_id:
        params["customer_id"] = customer_id

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                BASE_URL,
                headers=HEADERS,
                params=params,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()

            # Filter and format the response
            orders = [
                {
                    "id": order.get("id"),
                    "status": order.get("status"),
                    "date_created": order.get("date_created"),
                    "customer_id": order.get("customer_id"),
                    "total_inc_tax": order.get("total_inc_tax")
                }
                for order in result
            ]
            return {
                "orders": orders,
                "total_count": len(orders),
                "page": page,
                "limit": limit
            }

        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP error: {e.response.status_code} - {e.response.text}"}
        except Exception as e:
            return {"error": str(e)}

@mcp.tool(description="Update the status of an order by order ID.")
async def update_order_status(
    order_id: int,
    status: str
) -> dict:
    """
    Update the status of a specific order in BigCommerce.
    """
    global STORE_HASH
    global ACCESS_TOKEN

    STATUS_MAP = {
        "Incomplete": 0,
        "Pending": 1,
        "Shipped": 2,
        "Partially Shipped": 3,
        "Refunded": 4,
        "Cancelled": 5,
        "Awaiting Payment": 6,
        "Awaiting Fulfillment": 7,
        "Awaiting Shipment": 8,
        "Awaiting Pickup": 9,
        "Completed": 10,
        "Manual Verification Required": 11,
        "Disputed": 12,
        "Partially Refunded": 13
    }

    status_id = STATUS_MAP.get(status)
    if status_id is None:
        return {"error": f"Invalid status: {status}"}

    BASE_URL = f"https://api.bigcommerce.com/stores/{STORE_HASH}/v2/orders/{order_id}/status"
    HEADERS = {
        "X-Auth-Token": ACCESS_TOKEN,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    data = {"status_id": status_id}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.put(
                BASE_URL,
                headers=HEADERS,
                json=data,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()

            return {
                "id": result.get("id"),
                "status": status,
                "date_modified": result.get("date_modified"),
                "customer_id": result.get("customer_id"),
                "total_inc_tax": result.get("total_inc_tax")
            }

        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP error: {e.response.status_code} - {e.response.text}"}
        except Exception as e:
            return {"error": str(e)}
        
@mcp.tool(description="Get the current inventory (stock level) for a specific product.")
async def get_product_inventory(
    product_id: int
) -> dict:
    """
    Retrieve the current inventory (stock level) for a product in BigCommerce.

    Args:
        product_id: The unique ID of the product to check.

    Returns:
        Dict containing product inventory information or an error message.

    Example Response:
        {
            "product_id": 123,
            "name": "Product Name",
            "inventory_level": 50,
            "inventory_tracking": "product"
        }
    """
    global STORE_HASH
    global ACCESS_TOKEN

    BASE_URL = f"https://api.bigcommerce.com/stores/{STORE_HASH}/v3/catalog/products/{product_id}?include=variants"
    HEADERS = {
        "X-Auth-Token": ACCESS_TOKEN,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                BASE_URL,
                headers=HEADERS,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()

            data = result.get("data", {})
            inventory_tracking = data.get("inventory_tracking")
            inventory_level = data.get("inventory_level")
            name = data.get("name")

            # If inventory is tracked at the variant level, sum variant inventory
            if inventory_tracking == "variant":
                variants = data.get("variants", [])
                total_inventory = sum(
                    v.get("inventory_level", 0) for v in variants if v.get("inventory_level") is not None
                )
                return {
                    "product_id": product_id,
                    "name": name,
                    "inventory_tracking": inventory_tracking,
                    "total_inventory": total_inventory,
                    "variants": [
                        {
                            "variant_id": v.get("id"),
                            "sku": v.get("sku"),
                            "inventory_level": v.get("inventory_level")
                        }
                        for v in variants
                    ]
                }
            # If inventory is tracked at the product level
            else:
                return {
                    "product_id": product_id,
                    "name": name,
                    "inventory_tracking": inventory_tracking,
                    "inventory_level": inventory_level
                }

        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP error: {e.response.status_code} - {e.response.text}"}
        except Exception as e:
            return {"error": str(e)}
        
@mcp.tool(description="Process a full refund for a specific order by order ID.")
async def create_order_refund(
    order_id: int,
    reason: str
) -> dict:
    """
    Issue a full refund for the specified order in BigCommerce.

    Args:
        order_id: The unique ID of the order to refund.
        reason: The reason for the refund (e.g., 'BROKEN-ITEM', 'Customer request').

    Returns:
        Dict containing confirmation of the refund or an error message.

    Example Response:
        {
            "id": 302,
            "order_id": 1008,
            "transaction_type": "refund",
            "amount": "49.99",
            "status": "successful",
            "created_at": "2025-05-20T15:10:00Z"
        }
    """
    global STORE_HASH
    global ACCESS_TOKEN

    BASE_URL = f"https://api.bigcommerce.com/stores/{STORE_HASH}/v2/orders/{order_id}/payment_actions/refund"
    HEADERS = {
        "X-Auth-Token": ACCESS_TOKEN,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    # Full refund action
    data = {
        "reason": reason,
        "refund_to_original_payment": True
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                BASE_URL,
                headers=HEADERS,
                json=data,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()

            return {
                "id": result.get("id"),
                "order_id": result.get("order_id"),
                "transaction_type": result.get("transaction_type"),
                "amount": result.get("amount"),
                "status": result.get("status"),
                "created_at": result.get("created_at")
            }

        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP error: {e.response.status_code} - {e.response.text}"}
        except Exception as e:
            return {"error": str(e)}

@mcp.tool(description="Creates one or more customers in BigCommerce. Required fields: email, first_name, last_name. Optionally, you can add company, phone, notes, addresses, attributes, authentication, and more. You can create up to 10 customers in one call.")
async def create_customer(customers: list) -> dict:
    """
    Create up to 10 customers in BigCommerce.

    Required fields per customer:
        - email (string): Customer's email (unique, 3-250 chars)
        - first_name (string): Customer's first name (1-100 chars)
        - last_name (string): Customer's last name (1-100 chars)

    Optional fields:
        - company (string): Company name
        - phone (string): Phone number
        - notes (string): Notes about the customer
        - tax_exempt_category (string)
        - customer_group_id (int)
        - addresses (list): Up to 10 addresses per customer
            * Each address requires: first_name, last_name, address1, city, country_code
        - attributes (list): Up to 10 attributes per customer
            * Each attribute requires: attribute_id, attribute_value
        - authentication (dict): For password setup/reset
        - accepts_product_review_abandoned_cart_emails (bool)
        - trigger_account_created_notification (bool)
        - store_credit_amounts (list)
        - origin_channel_id (int)
        - channel_ids (list of int)
        - form_fields (list of dict)

    Example:
        customers = [
            {
                "email": "jane.doe@example.com",
                "first_name": "Jane",
                "last_name": "Doe",
                "company": "Example Inc.",
                "phone": "1234567890",
                "notes": "VIP customer",
                "addresses": [
                    {
                        "first_name": "Jane",
                        "last_name": "Doe",
                        "address1": "123 Main St",
                        "city": "San Francisco",
                        "country_code": "US"
                    }
                ]
            }
        ]

    Returns:
        On success: List of created customers with key details.
        On error: Error message explaining what went wrong.
    """
    # Validate input
    if not isinstance(customers, list) or not customers:
        return {"error": "Please provide a list of 1 to 10 customer objects."}
    if len(customers) > 10:
        return {"error": "You can only create up to 10 customers in one call."}

    # Validate required fields for each customer
    for idx, cust in enumerate(customers):
        missing = [f for f in ("email", "first_name", "last_name") if not cust.get(f)]
        if missing:
            return {"error": f"Customer {idx+1} is missing required fields: {', '.join(missing)}"}

        # Validate addresses if present
        if "addresses" in cust:
            for aidx, addr in enumerate(cust["addresses"]):
                required_addr = [f for f in ("first_name", "last_name", "address1", "city", "country_code") if not addr.get(f)]
                if required_addr:
                    return {"error": f"Customer {idx+1}, address {aidx+1} missing required fields: {', '.join(required_addr)}"}

        # Validate attributes if present
        if "attributes" in cust:
            for atidx, attr in enumerate(cust["attributes"]):
                if not attr.get("attribute_id") or not attr.get("attribute_value"):
                    return {"error": f"Customer {idx+1}, attribute {atidx+1} missing attribute_id or attribute_value."}

    global STORE_HASH
    global ACCESS_TOKEN

    BASE_URL = f"https://api.bigcommerce.com/stores/{STORE_HASH}/v3/customers"
    HEADERS = {
        "X-Auth-Token": ACCESS_TOKEN,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                BASE_URL,
                headers=HEADERS,
                json=customers,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()

            # Return filtered customer details
            if "data" in result and isinstance(result["data"], list):
                filtered = []
                for cust in result["data"]:
                    filtered.append({
                        "id": cust.get("id"),
                        "email": cust.get("email"),
                        "first_name": cust.get("first_name"),
                        "last_name": cust.get("last_name"),
                        "company": cust.get("company"),
                        "phone": cust.get("phone"),
                        "date_created": cust.get("date_created"),
                        "address_count": cust.get("address_count"),
                        "attribute_count": cust.get("attribute_count")
                    })
                return {"customers": filtered}
            return result

        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP error: {e.response.status_code} - {e.response.text}"}
        except Exception as e:
            return {"error": str(e)}

@mcp.tool(description="Lists customers from BigCommerce. Supports pagination and filtering by date created. Returns customer data and pagination info.")
async def list_customers(
    page: int = 1,
    limit: int = 50,
    date_created_min: str = None,
    date_created_max: str = None
) -> dict:
    """
    List customers from BigCommerce.

    Args:
        page (int): Page number (default 1)
        limit (int): Number of customers per page (default 50, max 250)
        date_created_min (str): Filter customers created after this date (ISO 8601, optional)
        date_created_max (str): Filter customers created before this date (ISO 8601, optional)

    Returns:
        On success: Dict with customer data and pagination info.
        On error: Error message explaining what went wrong.
    """
    global STORE_HASH
    global ACCESS_TOKEN

    url = f"https://api.bigcommerce.com/stores/{STORE_HASH}/v3/customers"
    headers = {
        "X-Auth-Token": ACCESS_TOKEN,
        "Accept": "application/json"
    }
    params = {
        "page": page,
        "limit": limit
    }
    if date_created_min:
        params["date_created:min"] = date_created_min
    if date_created_max:
        params["date_created:max"] = date_created_max

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params, timeout=30.0)
            response.raise_for_status()
            result = response.json()

            # Filter customer data for clarity
            if "data" in result and isinstance(result["data"], list):
                customers = []
                for cust in result["data"]:
                    customers.append({
                        "id": cust.get("id"),
                        "email": cust.get("email"),
                        "first_name": cust.get("first_name"),
                        "last_name": cust.get("last_name"),
                        "company": cust.get("company"),
                        "phone": cust.get("phone"),
                        "date_created": cust.get("date_created"),
                        "address_count": cust.get("address_count"),
                        "attribute_count": cust.get("attribute_count")
                    })
                return {
                    "customers": customers,
                    "pagination": result.get("meta", {}).get("pagination", {})
                }
            return result

        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP error: {e.response.status_code} - {e.response.text}"}
        except Exception as e:
            return {"error": str(e)}




        
if __name__ == "__main__":
    asyncio.run(mcp.run_sse_async(host="0.0.0.0", port=9100))