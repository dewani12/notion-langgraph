from typing import TypedDict, Annotated, Optional
from langgraph.graph import add_messages, StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessageChunk, SystemMessage
from dotenv import load_dotenv
from langchain_tavily import TavilySearch
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import re
from uuid import uuid4
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode

load_dotenv()

memory = MemorySaver()

class State(TypedDict):
    messages: Annotated[list, add_messages]

search_tool = TavilySearch(max_results=4)

tools = [search_tool]

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")

llm_with_tools = llm.bind_tools(tools=tools)

SYSTEM_MESSAGE = SystemMessage(content="""
You are Notion AI, a smart and flexible content assistant inside a Notion-like workspace. Your job is to help users generate **any type of content** — documents, code, guides, lists, strategies, summaries, or creative writing — depending on the user's intent.

Here’s how to behave:

1. Be flexible: Support structured and unstructured content (technical, creative, professional, or casual).
2. Allow code: If the user wants to include code (like Python, JS, SQL, etc.), format it cleanly using markdown (```) syntax.
3. Use tools when needed: If the user asks for real-world examples or insights, use the search tool to fetch accurate and recent references.
4. Adapt your tone: Keep responses clear, helpful, and Notion-style minimal — but adapt to the user's style or prompt.

Default structure when the user doesn’t specify:
---
## Title or Heading

### Brief Intro
---

### Section 1: Key Insight or Explanation
---

### Section 2: Example / Use Case / Code / Data
---

### Section 3: Summary / Takeaway / Framework
---

### Final Thought (if needed)aph
---
""")


class StreamingContentParser:
    def __init__(self):
        self.content_buffer = ""
        self.current_block_type = None
        self.in_code_block = False
        self.code_language = None
        self.block_id_counter = 0
        self.in_table = False
        self.table_headers = [] 
        
    def generate_block_id(self) -> str:
        """Generate unique block ID"""
        self.block_id_counter += 1
        return f"block_{self.block_id_counter}_{str(uuid4())[:8]}" # block_1_f563gf
    
    def detect_block_start(self, content: str) -> Optional[dict]:
        """Detect if content starts a new block"""
        content = content.strip()
        
        if not content:
            return None
            
        # Code block detection
        if content.startswith('```'):
            self.in_code_block = True
            language = content[3:].strip() or 'text'
            self.code_language = self.detect_language_from_marker(language)
            return {
                'type': 'code',
                'language': self.code_language,
                'block_id': self.generate_block_id(),
                'action': 'start',
                'metadata': {
                    'language': self.code_language,
                    'syntax_highlighting': True
                }
            }
        
        # End of code block
        if content == '```' and self.in_code_block:
            self.in_code_block = False
            return {
                'type': 'code',
                'action': 'end'
            }
        
        # Headings
        if content.startswith('# '):
            heading_content = content[2:].strip()
            return {
                'type': 'heading_1',
                'content': heading_content,
                'block_id': self.generate_block_id(),
                'metadata': {
                    'level': 1
                }
            }
        elif content.startswith('## '):
            heading_content = content[3:].strip()
            return {
                'type': 'heading_2',
                'content': heading_content,
                'block_id': self.generate_block_id(),
                'metadata': {
                    'level': 2
                }
            }
        elif content.startswith('### '):
            heading_content = content[4:].strip()
            return {
                'type': 'heading_3',
                'content': heading_content,
                'block_id': self.generate_block_id(),
                'metadata': {
                    'level': 3
                }
            }
        
        # Lists
        if content.startswith(('- ', '* ', '+ ')):
            return {
                'type': 'bulleted_list_item',
                'content': content[2:].strip(),
                'block_id': self.generate_block_id(),
                'metadata': {
                    'list_type': 'bulleted',
                    'marker': content[0]
                }
            }
        
        if re.match(r'^\d+\. ', content):
            number = re.match(r'^(\d+)\.', content).group(1)
            return {
                'type': 'numbered_list_item',
                'content': re.sub(r'^\d+\. ', '', content).strip(),
                'block_id': self.generate_block_id(),
                'metadata': {
                    'list_type': 'numbered',
                    'number': int(number)
                }
            }
        
        # Quote
        if content.startswith('> '):
            return {
                'type': 'quote',
                'content': content[2:].strip(),
                'block_id': self.generate_block_id(),
                'metadata': {
                    'quote_style': 'default'
                }
            }
        
        # Divider
        if re.match(r'^-{3,}$', content):
            return {
                'type': 'divider',
                'block_id': self.generate_block_id(),
                'metadata': {
                    'style': 'line'
                }
            }
        
        # Table detection
        if content.startswith('|') and content.endswith('|'):
            cells = [cell.strip() for cell in content[1:-1].split('|')]
            if not self.in_table:
                self.in_table = True
                self.table_headers = cells
                return {
                    'type': 'table',
                    'subtype': 'header',
                    'content': cells,
                    'block_id': self.generate_block_id(),
                    'metadata': {
                        'column_count': len(cells),
                        'headers': cells,
                        'is_header': True
                    }
                }
            else:
                return {
                    'type': 'table',
                    'subtype': 'row',
                    'content': cells,
                    'metadata': {
                        'column_count': len(cells),
                        'headers': self.table_headers,
                        'is_header': False
                    }
                }
        else:
            # Reset table state if we're no longer in a table
            if self.in_table:
                self.in_table = False
                self.table_headers = []
        
        return None
    
    def detect_language_from_marker(self, marker: str) -> str:
        """Detect programming language from code block marker"""
        language_map = {
            'py': 'python',
            'js': 'javascript',
            'ts': 'typescript',
            'jsx': 'javascript',
            'tsx': 'typescript',
            'html': 'html',
            'css': 'css',
            'sql': 'sql',
            'json': 'json',
            'yaml': 'yaml',
            'yml': 'yaml',
            'md': 'markdown',
            'sh': 'bash',
            'bash': 'bash'
        }
        return language_map.get(marker.lower(), marker.lower() if marker else 'text')
    
    def classify_content_type(self, content: str) -> str:
        """Classify content type for frontend rendering"""
        if self.in_code_block:
            return 'code_content'
        
        # Check for inline code
        if '`' in content and content.count('`') >= 2:
            return 'text_with_code'
        
        # Check for bold/italic formatting
        if '**' in content or '*' in content:
            return 'text_with_formatting'
        
        # Check for links
        if re.search(r'\[([^\]]+)\]\(([^)]+)\)', content):
            return 'text_with_links'
        
        # Check for special characters or symbols
        if re.search(r'[→←↑↓✓✗➜➤▶▷]', content):
            return 'text_with_symbols'
        
        return 'plain_text'
    
    def analyze_content_metadata(self, content: str) -> dict:
        """Analyze content and return metadata"""
        metadata = {
            'word_count': len(content.split()),
            'char_count': len(content),
            'has_formatting': False,
            'has_links': False,
            'has_inline_code': False
        }
        
        # Check for formatting
        if re.search(r'\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`', content):
            metadata['has_formatting'] = True
        
        # Check for links
        if re.search(r'\[([^\]]+)\]\(([^)]+)\)', content):
            metadata['has_links'] = True
        
        # Check for inline code
        if '`' in content:
            metadata['has_inline_code'] = True
        
        return metadata

async def model(state: State):
    result = await llm_with_tools.ainvoke(state["messages"])
    return {
        "messages": [result], 
    }

async def tools_router(state: State):
    last_message = state["messages"][-1]

    if(hasattr(last_message, "tool_calls") and len(last_message.tool_calls) > 0):
        return "tool_node"
    else: 
        return END
    
tool_node = ToolNode(tools=tools)

graph_builder = StateGraph(State)

graph_builder.add_node("model", model)
graph_builder.add_node("tool_node", tool_node)
graph_builder.set_entry_point("model")

graph_builder.add_conditional_edges("model", tools_router,{
    "tool_node": "tool_node",
    END: END,
})
graph_builder.add_edge("tool_node", "model")

graph = graph_builder.compile(checkpointer=memory)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"], 
    expose_headers=["Content-Type"], 
)

def serialise_ai_message_chunk(chunk): 
    if(isinstance(chunk, AIMessageChunk)):
        return chunk.content
    else:
        raise TypeError(
            f"Object of type {type(chunk).__name__} is not correctly formatted for serialisation"
        )

async def generate_chat_responses(message: str, checkpoint_id: Optional[str] = None):
    is_new_conversation = checkpoint_id is None
    
    if is_new_conversation:
        new_checkpoint_id = str(uuid4())

        config = {
            "configurable": {
                "thread_id": new_checkpoint_id
            }
        }
        
        events = graph.astream_events(
            {"messages": [SYSTEM_MESSAGE,HumanMessage(content=message)]},
            version="v2",
            config=config
        )
        
        yield f"data: {{\"type\": \"checkpoint\", \"checkpoint_id\": \"{new_checkpoint_id}\"}}\n\n"
    else:
        config = {
            "configurable": {
                "thread_id": checkpoint_id
            }
        }
        events = graph.astream_events(
            {"messages": [SYSTEM_MESSAGE,HumanMessage(content=message)]},
            version="v2",
            config=config
        )

    async for event in events:
        event_type = event["event"]
        
        if event_type == "on_chat_model_stream":
            chunk_content = serialise_ai_message_chunk(event["data"]["chunk"])
            safe_content = chunk_content.replace("'", "\\'").replace("\n", "\\n")
            
            yield f"data: {{\"type\": \"content\", \"content\": \"{safe_content}\"}}\n\n"
            
        elif event_type == "on_chat_model_end":
            tool_calls = event["data"]["output"].tool_calls if hasattr(event["data"]["output"], "tool_calls") else []
            search_calls = [call for call in tool_calls if call["name"] == "tavily_search_results_json"]
            
            if search_calls:
                search_query = search_calls[0]["args"].get("query", "")
                safe_query = search_query.replace('"', '\\"').replace("'", "\\'").replace("\n", "\\n")
                yield f"data: {{\"type\": \"search_start\", \"query\": \"{safe_query}\"}}\n\n"
                
        elif event_type == "on_tool_end" and event["name"] == "tavily_search_results_json":
            output = event["data"]["output"]
            
            # Check if output is a list 
            if isinstance(output, list):
                urls = []
                for item in output:
                    if isinstance(item, dict) and "url" in item:
                        urls.append(item["url"])
                
                urls_json = json.dumps(urls)
                yield f"data: {{\"type\": \"search_results\", \"urls\": {urls_json}}}\n\n"
    
    yield f"data: {{\"type\": \"end\"}}\n\n"

async def generate_enhanced_chat_responses(message: str, checkpoint_id: Optional[str] = None):
    """Enhanced streaming with block detection and content classification"""
    parser = StreamingContentParser()
    content_buffer = ""
    
    is_new_conversation = checkpoint_id is None
    
    if is_new_conversation:
        new_checkpoint_id = str(uuid4())
        config = {
            "configurable": {
                "thread_id": new_checkpoint_id
            }
        }
        events = graph.astream_events(
            {"messages": [SYSTEM_MESSAGE, HumanMessage(content=message)]},
            version="v2",
            config=config
        )
        yield f"data: {{\"type\": \"checkpoint\", \"checkpoint_id\": \"{new_checkpoint_id}\"}}\n\n"
    else:
        config = {
            "configurable": {
                "thread_id": checkpoint_id
            }
        }
        events = graph.astream_events(
            {"messages": [SYSTEM_MESSAGE, HumanMessage(content=message)]},
            version="v2",
            config=config
        )

    async for event in events:
        event_type = event["event"]
        
        if event_type == "on_chat_model_stream":
            chunk_content = serialise_ai_message_chunk(event["data"]["chunk"])
            content_buffer += chunk_content
            
            # Check for line breaks to process complete lines
            if '\n' in content_buffer:
                lines = content_buffer.split('\n')
                # Keep the last incomplete line in buffer
                content_buffer = lines[-1]
                
                # Process complete lines
                for line in lines[:-1]:
                    if line.strip():
                        # Detect block type
                        block_info = parser.detect_block_start(line)
                        content_type = parser.classify_content_type(line)
                        content_metadata = parser.analyze_content_metadata(line)
                        
                        if block_info:
                            # Send block metadata
                            block_data = {
                                "type": "block_start",
                                "block_info": block_info,
                                "content_type": content_type,
                                "content_metadata": content_metadata
                            }
                            yield f"data: {json.dumps(block_data)}\n\n"
                        
                        # Send content with type information
                        content_data = {
                            "type": "content",
                            "content": line,
                            "content_type": content_type,
                            "content_metadata": content_metadata,
                            "in_code_block": parser.in_code_block,
                            "code_language": parser.code_language if parser.in_code_block else None,
                            "in_table": parser.in_table
                        }
                        
                        yield f"data: {json.dumps(content_data)}\n\n"
                    else:
                        # Empty line - potential block separator
                        yield f"data: {{\"type\": \"line_break\"}}\n\n"
            else:
                # Send chunk as is for inline content
                if chunk_content.strip():  # Only send non-empty chunks
                    content_type = parser.classify_content_type(chunk_content)
                    content_metadata = parser.analyze_content_metadata(chunk_content)
                    
                    content_data = {
                        "type": "content_chunk",
                        "content": chunk_content,
                        "content_type": content_type,
                        "content_metadata": content_metadata,
                        "in_code_block": parser.in_code_block,
                        "code_language": parser.code_language if parser.in_code_block else None,
                        "in_table": parser.in_table
                    }
                    yield f"data: {json.dumps(content_data)}\n\n"
                
        elif event_type == "on_chat_model_end":
            # Process any remaining content in buffer
            if content_buffer.strip():
                block_info = parser.detect_block_start(content_buffer)
                content_type = parser.classify_content_type(content_buffer)
                content_metadata = parser.analyze_content_metadata(content_buffer)
                
                if block_info:
                    block_data = {
                        "type": "block_start",
                        "block_info": block_info,
                        "content_type": content_type,
                        "content_metadata": content_metadata
                    }
                    yield f"data: {json.dumps(block_data)}\n\n"
                
                content_data = {
                    "type": "content",
                    "content": content_buffer,
                    "content_type": content_type,
                    "content_metadata": content_metadata,
                    "in_code_block": parser.in_code_block,
                    "code_language": parser.code_language if parser.in_code_block else None,
                    "in_table": parser.in_table
                }
                yield f"data: {json.dumps(content_data)}\n\n"
            
            # Check for tool calls
            tool_calls = event["data"]["output"].tool_calls if hasattr(event["data"]["output"], "tool_calls") else []
            search_calls = [call for call in tool_calls if call["name"] == "tavily_search_results_json"]
            
            if search_calls:
                search_query = search_calls[0]["args"].get("query", "")
                search_data = {
                    "type": "search_start",
                    "query": search_query
                }
                yield f"data: {json.dumps(search_data)}\n\n"
                
        elif event_type == "on_tool_end" and event["name"] == "tavily_search_results_json":
            output = event["data"]["output"]
            
            if isinstance(output, list):
                urls = []
                search_results = []
                for item in output:
                    if isinstance(item, dict):
                        if "url" in item:
                            urls.append(item["url"])
                        # Extract more metadata if available
                        search_results.append({
                            "url": item.get("url", ""),
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", "")
                        })
                
                search_results_data = {
                    "type": "search_results",
                    "urls": urls,
                    "results": search_results,
                    "result_count": len(search_results)
                }
                yield f"data: {json.dumps(search_results_data)}\n\n"
    
    # Send completion signal with summary
    completion_data = {
    "type": "end",
    "summary": {
        "total_blocks": parser.block_id_counter,
        "had_code_blocks": parser.block_id_counter > 0 and hasattr(parser, 'code_language'),
        "had_tables": parser.in_table or bool(parser.table_headers)
    }
}

    yield f"data: {json.dumps(completion_data)}\n\n"

@app.get("/chat_stream/{message}")
async def chat_stream(message: str, checkpoint_id: Optional[str] = Query(None)):
    return StreamingResponse(
        generate_chat_responses(message, checkpoint_id), 
        media_type="text/event-stream"
    )

@app.get("/enhanced_chat_stream/{message}")
async def enhanced_chat_stream(message: str, checkpoint_id: Optional[str] = Query(None)):
    return StreamingResponse(
        generate_enhanced_chat_responses(message, checkpoint_id), 
        media_type="text/event-stream"
    )