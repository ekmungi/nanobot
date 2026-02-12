<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# I am using python API.

```markdown
# Notion API Extraction Limits & Requirements (Python)

## Critical Limits to Handle

### Text Content Limits
- **Rich text content**: 2,000 characters per `text.content` field
- **Rich text arrays**: Maximum 100 elements per array
- **Equation expressions**: 1,000 characters maximum
- **URLs**: 2,000 characters maximum

### Pagination Limits
- **Query results**: 100 items per API call (use pagination for more)
- **Block children**: 100 blocks per paginated response
- **Overall payload**: 1,000 block elements AND 500KB total size limit

### Array Limits
- **Relations**: Maximum 100 related pages
- **People mentions**: Maximum 100 users


## Page Extraction Requirements

### Retrieving Page Content
1. Use `client.blocks.children.list(block_id=block_id)` to get page blocks
2. Implement pagination using `start_cursor` when `has_more` is `True`
3. Each response returns max 100 blocks - continue until `has_more` is `False`

### Handling Large Text Blocks
- Text blocks may contain arrays of rich_text objects (max 100 per array)
- Each rich_text object has max 2,000 characters in `text.content`
- For complete text extraction: concatenate all rich_text objects in the array
- Check for nested blocks (blocks can contain children) - recursively fetch children

### Code Pattern for Page Extraction
```python
from notion_client import Client

notion = Client(auth="your_integration_token")

def get_all_page_blocks(block_id):
    """Retrieve all blocks from a page with pagination."""
    all_blocks = []
    has_more = True
    start_cursor = None
    
    while has_more:
        response = notion.blocks.children.list(
            block_id=block_id,
            start_cursor=start_cursor,
            page_size=100
        )
        
        all_blocks.extend(response.get("results", []))
        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")
    
    return all_blocks


def extract_text_from_block(block):
    """Extract text content from a block, handling rich_text arrays."""
    block_type = block.get("type")
    
    if block_type in ["paragraph", "heading_1", "heading_2", "heading_3", 
                       "bulleted_list_item", "numbered_list_item", "quote", 
                       "callout", "toggle"]:
        rich_text_array = block.get(block_type, {}).get("rich_text", [])
        return "".join([rt.get("plain_text", "") for rt in rich_text_array])
    
    elif block_type == "code":
        rich_text_array = block.get("code", {}).get("rich_text", [])
        return "".join([rt.get("plain_text", "") for rt in rich_text_array])
    
    return ""


def get_all_page_content(page_id):
    """Get all text content from a page, handling nested blocks."""
    blocks = get_all_page_blocks(page_id)
    content = []
    
    for block in blocks:
        text = extract_text_from_block(block)
        if text:
            content.append(text)
        
        # Handle nested blocks recursively
        if block.get("has_children"):
            nested_content = get_all_page_content(block["id"])
            content.extend(nested_content)
    
    return content
```


## Database Extraction Requirements

### Querying Database Entries

1. Use `client.databases.query(database_id=database_id)`
2. Results limited to 100 per request - implement pagination
3. Use `start_cursor` from response to fetch next page
4. Continue until `has_more` is `False`

### Database Property Extraction

- Each property type has different structure (rich_text, number, select, multi_select, etc.)
- **Rich text properties**: Follow same 2,000 char limit per object, max 100 objects
- **Title properties**: Same as rich_text (array of objects, each max 2,000 chars)
- **Relation properties**: Max 100 related pages per property


### Code Pattern for Database Extraction

```python
def get_all_database_entries(database_id, filter_conditions=None):
    """Retrieve all entries from a database with pagination."""
    all_pages = []
    has_more = True
    start_cursor = None
    
    while has_more:
        query_params = {
            "database_id": database_id,
            "start_cursor": start_cursor,
            "page_size": 100
        }
        
        if filter_conditions:
            query_params["filter"] = filter_conditions
        
        response = notion.databases.query(**query_params)
        
        all_pages.extend(response.get("results", []))
        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")
    
    return all_pages


def extract_property_value(property_data):
    """Extract value from a Notion property based on its type."""
    prop_type = property_data.get("type")
    
    if prop_type == "title":
        return "".join([t.get("plain_text", "") for t in property_data.get("title", [])])
    
    elif prop_type == "rich_text":
        return "".join([t.get("plain_text", "") for t in property_data.get("rich_text", [])])
    
    elif prop_type == "number":
        return property_data.get("number")
    
    elif prop_type == "select":
        select_data = property_data.get("select")
        return select_data.get("name") if select_data else None
    
    elif prop_type == "multi_select":
        return [ms.get("name") for ms in property_data.get("multi_select", [])]
    
    elif prop_type == "date":
        date_data = property_data.get("date")
        if date_data:
            return {
                "start": date_data.get("start"),
                "end": date_data.get("end")
            }
        return None
    
    elif prop_type == "checkbox":
        return property_data.get("checkbox")
    
    elif prop_type == "url":
        return property_data.get("url")
    
    elif prop_type == "email":
        return property_data.get("email")
    
    elif prop_type == "phone_number":
        return property_data.get("phone_number")
    
    elif prop_type == "relation":
        return [rel.get("id") for rel in property_data.get("relation", [])]
    
    elif prop_type == "people":
        return [person.get("id") for person in property_data.get("people", [])]
    
    elif prop_type == "files":
        return [f.get("name") for f in property_data.get("files", [])]
    
    elif prop_type == "status":
        status_data = property_data.get("status")
        return status_data.get("name") if status_data else None
    
    return None


def extract_all_properties(page):
    """Extract all properties from a database page."""
    properties = page.get("properties", {})
    extracted = {}
    
    for prop_name, prop_data in properties.items():
        extracted[prop_name] = extract_property_value(prop_data)
    
    return extracted


# Usage example
database_pages = get_all_database_entries("your_database_id")
for page in database_pages:
    page_data = extract_all_properties(page)
    print(page_data)
```


## Error Handling \& Rate Limiting

### Rate Limit Handling

```python
import time
from notion_client import APIResponseError

def safe_api_call(api_function, *args, **kwargs):
    """Wrapper for API calls with retry logic and rate limiting."""
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            response = api_function(*args, **kwargs)
            time.sleep(0.34)  # Respect 3 req/sec limit (1/3 = 0.333s)
            return response
        
        except APIResponseError as e:
            if e.code == 429:  # Rate limited
                wait_time = 2 ** retry_count  # Exponential backoff
                print(f"Rate limited. Waiting {wait_time}s...")
                time.sleep(wait_time)
                retry_count += 1
            else:
                raise e
    
    raise Exception(f"Failed after {max_retries} retries")


# Usage
response = safe_api_call(notion.databases.query, database_id="your_db_id")
```


## Complete Example: Extract Full Database with Page Content

```python
def extract_full_database_with_content(database_id):
    """Extract database entries and their full page content."""
    # Get all database entries
    entries = get_all_database_entries(database_id)
    
    full_data = []
    
    for entry in entries:
        # Extract properties
        properties = extract_all_properties(entry)
        
        # Extract full page content
        page_id = entry["id"]
        content = get_all_page_content(page_id)
        
        full_data.append({
            "id": page_id,
            "properties": properties,
            "content": content
        })
        
        # Rate limiting
        time.sleep(0.34)
    
    return full_data


# Usage
data = extract_full_database_with_content("your_database_id")
```


## Implementation Checklist

**For Page Extraction:**

- [ ] Implement pagination loop with `has_more` check
- [ ] Handle nested blocks (recursively fetch children when `has_children` is `True`)
- [ ] Concatenate rich_text arrays to get complete text
- [ ] Handle all block types needed (paragraph, heading, code, bullet_list, etc.)
- [ ] Add rate limit handling (0.34s delay between calls = 3 req/sec)

**For Database Extraction:**

- [ ] Implement pagination loop with `has_more` check
- [ ] Parse all relevant property types correctly
- [ ] Extract and concatenate rich_text/title arrays
- [ ] Handle relation properties if needed (may require additional API calls)
- [ ] Add rate limit handling (0.34s delay between calls)

**General:**

- [ ] Add error handling for API failures
- [ ] Implement retry logic with exponential backoff for 429 errors
- [ ] Log progress for large extractions (use `tqdm` for progress bars)
- [ ] Validate extracted data completeness
- [ ] Install required package: `pip install notion-client`

```

**Instructions for Claude Code:**
This document outlines Notion API constraints for Python extraction. Use the `notion-client` library. Implement pagination for all queries (100 item limit), handle rich_text arrays by concatenating `plain_text` fields, respect rate limits (add 0.34s delay between calls), and implement exponential backoff for 429 errors. The provided code patterns are production-ready templates you can adapt.```

