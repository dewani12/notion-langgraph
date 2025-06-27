from typing import TypedDict, Annotated, Optional, Dict, Any, List
from langgraph.graph import add_messages, StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessageChunk, SystemMessage
from dotenv import load_dotenv
from langchain_tavily import TavilySearch
from langchain_groq import ChatGroq
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import re
from uuid import uuid4
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from enum import Enum

load_dotenv()

memory = MemorySaver()

class State(TypedDict):
    messages: Annotated[list, add_messages]

class BlockType(Enum):
    HEADING_1 = "heading_1"
    HEADING_2 = "heading_2"
    HEADING_3 = "heading_3"
    HEADING_4 = "heading_4"
    HEADING_5 = "heading_5"
    HEADING_6 = "heading_6"
    PARAGRAPH = "paragraph"
    CODE_BLOCK = "code_block"
    BULLETED_LIST = "bulleted_list_item"
    NUMBERED_LIST = "numbered_list_item"
    QUOTE = "quote"
    DIVIDER = "divider"
    TABLE = "table"
    CALLOUT = "callout"

class ContentType(Enum):
    PLAIN_TEXT = "plain_text"
    MARKDOWN = "markdown"
    CODE = "code"
    TEXT_WITH_FORMATTING = "text_with_formatting"
    TEXT_WITH_LINKS = "text_with_links"
    TEXT_WITH_CODE = "text_with_code"

search_tool = TavilySearch(max_results=4)
tools = [search_tool]
# llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")
llm=ChatGroq(model="llama3-8b-8192")
llm_with_tools = llm.bind_tools(tools=tools)

SYSTEM_MESSAGE = SystemMessage(content="""
You are Notion AI, a smart and flexible content assistant inside a Notion-like workspace. Your job is to help users generate **any type of content** — documents, code, guides, lists, strategies, summaries, or creative writing — depending on the user's intent.

Here's how to behave:

1. Be flexible: Support structured and unstructured content (technical, creative, professional, or casual).
2. Allow code: If the user wants to include code (like Python, JS, SQL, etc.), format it cleanly using markdown (```) syntax.
3. Use tools when needed: If the user asks for real-world examples or insights, use the search tool to fetch accurate and recent references.
4. Adapt your tone: Keep responses clear, helpful, and Notion-style minimal — but adapt to the user's style or prompt.

Default structure when the user doesn't specify:
---
### Title or Heading
---

### Brief Intro
---

### Section 1: Key Insight or Explanation
---

### Section 2: Example / Use Case / Code / Data
---

### Section 3: Summary / Takeaway / Framework
---

### Final Thought (if needed)
---
""")

class EnhancedStreamingContentParser:
    def __init__(self):
        self.content_buffer = ""
        self.current_block = None
        self.block_id_counter = 0
        self.in_code_block = False
        self.code_language = None
        self.in_table = False
        self.table_headers = []
        self.current_list_type = None
        self.current_list_items = []
        self.processed_lines = []
        
    def generate_block_id(self) -> str:
        """Generate unique block ID"""
        self.block_id_counter += 1
        return f"block_{self.block_id_counter}_{str(uuid4())[:8]}"
    
    def detect_language(self, marker: str) -> str:
        """Enhanced language detection"""
        language_map = {
            'py': 'python', 'python': 'python',
            'js': 'javascript', 'javascript': 'javascript',
            'ts': 'typescript', 'typescript': 'typescript',
            'jsx': 'javascript', 'tsx': 'typescript',
            'html': 'html', 'htm': 'html',
            'css': 'css', 'scss': 'scss', 'sass': 'sass',
            'sql': 'sql', 'mysql': 'sql', 'postgresql': 'sql',
            'json': 'json', 'yaml': 'yaml', 'yml': 'yaml',
            'xml': 'xml', 'md': 'markdown', 'markdown': 'markdown',
            'sh': 'bash', 'bash': 'bash', 'zsh': 'bash',
            'r': 'r', 'go': 'go', 'rust': 'rust', 'rs': 'rust',
            'java': 'java', 'c': 'c', 'cpp': 'cpp', 'c++': 'cpp',
            'cs': 'csharp', 'csharp': 'csharp', 'c#': 'csharp',
            'php': 'php', 'rb': 'ruby', 'ruby': 'ruby',
            'swift': 'swift', 'kt': 'kotlin', 'kotlin': 'kotlin',
            'dart': 'dart', 'scala': 'scala', 'clj': 'clojure'
        }
        return language_map.get(marker.lower().strip(), marker.lower().strip() if marker else 'text')
    
    def analyze_content_metadata(self, content: str) -> Dict[str, Any]:
        """Enhanced content analysis"""
        words = content.split()
        metadata = {
            'word_count': len(words),
            'char_count': len(content),
            'line_count': content.count('\n') + 1,
            'has_formatting': bool(re.search(r'\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|~~[^~]+~~', content)),
            'has_links': bool(re.search(r'\[([^\]]+)\]\(([^)]+)\)', content)),
            'has_inline_code': '`' in content and not content.strip().startswith('```'),
            'has_images': bool(re.search(r'!\[([^\]]*)\]\(([^)]+)\)', content)),
            'has_bold': '**' in content,
            'has_italic': re.search(r'\*[^*]+\*(?!\*)', content) is not None,
            'has_strikethrough': '~~' in content,
            'has_lists': bool(re.search(r'^[\s]*[-*+]\s|^[\s]*\d+\.\s', content, re.MULTILINE)),
            'has_tables': '|' in content and content.count('|') >= 2,
            'has_quotes': content.strip().startswith('>'),
            'language': None
        }
        
        if self.in_code_block and self.code_language:
            metadata['language'] = self.code_language
            
        return metadata
    
    def classify_content_type(self, content: str) -> ContentType:
        """Classify content type for rendering"""
        if self.in_code_block:
            return ContentType.CODE
        
        metadata = self.analyze_content_metadata(content)
        
        if metadata['has_inline_code']:
            return ContentType.TEXT_WITH_CODE
        elif metadata['has_formatting']:
            return ContentType.TEXT_WITH_FORMATTING
        elif metadata['has_links']:
            return ContentType.TEXT_WITH_LINKS
        elif any([metadata['has_lists'], metadata['has_tables'], metadata['has_quotes']]):
            return ContentType.MARKDOWN
        else:
            return ContentType.PLAIN_TEXT
    
    def detect_block_type(self, line: str) -> Optional[Dict[str, Any]]:
        """Enhanced block type detection"""
        stripped = line.strip()
        if not stripped:
            return None
        
        # Code blocks
        if stripped.startswith('```'):
            if self.in_code_block:
                # End of code block
                self.in_code_block = False
                self.code_language = None
                return {
                    'type': BlockType.CODE_BLOCK.value,
                    'action': 'end',
                    'block_id': self.current_block['block_id'] if self.current_block else None
                }
            else:
                # Start of code block
                self.in_code_block = True
                language = stripped[3:].strip()
                self.code_language = self.detect_language(language)
                return {
                    'type': BlockType.CODE_BLOCK.value,
                    'language': self.code_language,
                    'block_id': self.generate_block_id(),
                    'action': 'start',
                    'metadata': {
                        'language': self.code_language,
                        'syntax_highlighting': True,
                        'executable': self.code_language in ['python', 'javascript', 'sql']
                    }
                }
        
        # Skip processing if inside code block
        if self.in_code_block:
            return None
        
        # Headings (H1-H6)
        heading_match = re.match(r'^(#{1,6})\s+(.+)', stripped)
        if heading_match:
            level = len(heading_match.group(1))
            content = heading_match.group(2).strip()
            return {
                'type': f"heading_{level}",
                'content': content,
                'block_id': self.generate_block_id(),
                'metadata': {
                    'level': level,
                    'text': content
                }
            }
        
        # Lists
        bullet_match = re.match(r'^[\s]*[-*+]\s+(.+)', stripped)
        if bullet_match:
            content = bullet_match.group(1).strip()
            return {
                'type': BlockType.BULLETED_LIST.value,
                'content': content,
                'block_id': self.generate_block_id(),
                'metadata': {
                    'list_type': 'bulleted',
                    'text': content,
                    'marker': stripped[0] if stripped[0] in '-*+' else '-'
                }
            }
        
        number_match = re.match(r'^[\s]*(\d+)\.\s+(.+)', stripped)
        if number_match:
            number = int(number_match.group(1))
            content = number_match.group(2).strip()
            return {
                'type': BlockType.NUMBERED_LIST.value,
                'content': content,
                'block_id': self.generate_block_id(),
                'metadata': {
                    'list_type': 'numbered',
                    'number': number,
                    'text': content
                }
            }
        
        # Quotes
        if stripped.startswith('> '):
            content = stripped[2:].strip()
            return {
                'type': BlockType.QUOTE.value,
                'content': content,
                'block_id': self.generate_block_id(),
                'metadata': {
                    'quote_style': 'default',
                    'text': content
                }
            }
        
        # Dividers
        if re.match(r'^-{3,}$|^\*{3,}$|^_{3,}$', stripped):
            return {
                'type': BlockType.DIVIDER.value,
                'block_id': self.generate_block_id(),
                'metadata': {
                    'style': 'line'
                }
            }
        
        # Tables
        if stripped.startswith('|') and stripped.endswith('|') and stripped.count('|') >= 2:
            cells = [cell.strip() for cell in stripped[1:-1].split('|')]
            if not self.in_table:
                self.in_table = True
                self.table_headers = cells
                return {
                    'type': BlockType.TABLE.value,
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
                    'type': BlockType.TABLE.value,
                    'subtype': 'row',
                    'content': cells,
                    'metadata': {
                        'column_count': len(cells),
                        'headers': self.table_headers,
                        'is_header': False
                    }
                }
        else:
            if self.in_table:
                self.in_table = False
                self.table_headers = []
        
        # Default paragraph
        if stripped:
            return {
                'type': BlockType.PARAGRAPH.value,
                'content': stripped,
                'block_id': self.generate_block_id(),
                'metadata': {
                    'text': stripped
                }
            }
        
        return None
    
    def process_content_chunk(self, chunk: str) -> List[Dict[str, Any]]:
        """Process content chunk and return structured blocks"""
        events = []
        self.content_buffer += chunk
        
        # Process complete lines
        if '\n' in self.content_buffer:
            lines = self.content_buffer.split('\n')
            self.content_buffer = lines[-1]  # Keep incomplete line
            
            for line in lines[:-1]:
                events.extend(self.process_line(line))
            
            # Send line break for empty lines
            if not lines[-2].strip():  # Check second to last line
                events.append({'type': 'line_break'})
        
        return events
    
    def process_line(self, line: str) -> List[Dict[str, Any]]:
        """Process a single line and return events"""
        events = []
        
        # Detect block type
        block_info = self.detect_block_type(line)
        
        if block_info:
            # End previous block if needed
            if self.current_block and block_info.get('action') != 'end':
                events.append({
                    'type': 'block_end',
                    'block_id': self.current_block.get('block_id', 'unknown_block')  # FIXED: Safe access
                })
            
            # Send block start event
            if block_info.get('action') != 'end':
                events.append({
                    'type': 'block_start',
                    'block_info': block_info
                })
                self.current_block = block_info
            else:
                self.current_block = None
        
        # Send content if not empty and not a block marker
        if line.strip() and not (line.strip().startswith('```') and not self.in_code_block):
            content_type = self.classify_content_type(line)
            content_metadata = self.analyze_content_metadata(line)
            
            events.append({
                'type': 'content',
                'content': line,
                'content_type': content_type.value,
                'metadata': content_metadata,
                'context': {
                    'in_code_block': self.in_code_block,
                    'code_language': self.code_language,
                    'in_table': self.in_table,
                    'block_type': self.current_block.get('type', 'paragraph') if self.current_block else 'paragraph'  # FIXED: Safe access
                }
            })
        
        return events
    
    def finalize(self) -> List[Dict[str, Any]]:
        """Process any remaining content and return final events"""
        events = []
        
        if self.content_buffer.strip():
            events.extend(self.process_line(self.content_buffer))
        
        # End any open blocks
        if self.current_block:
            events.append({
                'type': 'block_end',
                'block_id': self.current_block['block_id']
            })
        
        # Generate summary
        events.append({
            'type': 'end',
            'summary': {
                'total_blocks': self.block_id_counter,
                'content_types': list(set([event.get('content_type') for event in events if event.get('content_type')])),
                'had_code_blocks': any(event.get('block_info', {}).get('type') == BlockType.CODE_BLOCK.value for event in events),
                'had_tables': self.in_table or bool(self.table_headers),
                'total_words': sum(event.get('metadata', {}).get('word_count', 0) for event in events),
                'total_chars': sum(event.get('metadata', {}).get('char_count', 0) for event in events)
            }
        })
        
        return events

async def model(state: State):
    result = await llm_with_tools.ainvoke(state["messages"])
    return {"messages": [result]}

async def tools_router(state: State):
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and len(last_message.tool_calls) > 0:
        return "tool_node"
    else: 
        return END

tool_node = ToolNode(tools=tools)

graph_builder = StateGraph(State)
graph_builder.add_node("model", model)
graph_builder.add_node("tool_node", tool_node)
graph_builder.set_entry_point("model")

graph_builder.add_conditional_edges("model", tools_router, {
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
    if isinstance(chunk, AIMessageChunk):
        return chunk.content
    else:
        raise TypeError(f"Object of type {type(chunk).__name__} is not correctly formatted for serialisation")

async def generate_enhanced_chat_responses(message: str, checkpoint_id: Optional[str] = None):
    """Enhanced streaming with consistent block structure"""
    parser = EnhancedStreamingContentParser()
    
    # Handle conversation setup
    is_new_conversation = checkpoint_id is None
    
    if is_new_conversation:
        new_checkpoint_id = str(uuid4())
        config = {"configurable": {"thread_id": new_checkpoint_id}}
        events = graph.astream_events(
            {"messages": [SYSTEM_MESSAGE, HumanMessage(content=message)]},
            version="v2",
            config=config
        )
        yield f"data: {json.dumps({'type': 'checkpoint', 'checkpoint_id': new_checkpoint_id})}\n\n"
    else:
        config = {"configurable": {"thread_id": checkpoint_id}}
        events = graph.astream_events(
            {"messages": [SYSTEM_MESSAGE, HumanMessage(content=message)]},
            version="v2",
            config=config
        )

    # Process streaming events
    async for event in events:
        event_type = event["event"]
        
        if event_type == "on_chat_model_stream":
            chunk_content = serialise_ai_message_chunk(event["data"]["chunk"])
            
            # Process content through parser
            parsed_events = parser.process_content_chunk(chunk_content)
            
            for parsed_event in parsed_events:
                yield f"data: {json.dumps(parsed_event)}\n\n"
                
        elif event_type == "on_chat_model_end":
            # Process any remaining content
            final_events = parser.finalize()
            for final_event in final_events:
                yield f"data: {json.dumps(final_event)}\n\n"
            
            # Handle tool calls
            tool_calls = event["data"]["output"].tool_calls if hasattr(event["data"]["output"], "tool_calls") else []
            search_calls = [call for call in tool_calls if call["name"] == "tavily_search_results_json"]
            
            if search_calls:
                search_query = search_calls[0]["args"].get("query", "")
                search_data = {
                    "type": "search_start",
                    "query": search_query,
                    "timestamp": str(uuid4())
                }
                yield f"data: {json.dumps(search_data)}\n\n"
                
        elif event_type == "on_tool_end" and event["name"] == "tavily_search_results_json":
            output = event["data"]["output"]
            
            if isinstance(output, list):
                search_results = []
                for item in output:
                    if isinstance(item, dict):
                        search_results.append({
                            "url": item.get("url", ""),
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", ""),
                            "score": item.get("score", 0)
                        })
                
                search_results_data = {
                    "type": "search_results",
                    "results": search_results,
                    "result_count": len(search_results),
                    "urls": [r["url"] for r in search_results]
                }
                yield f"data: {json.dumps(search_results_data)}\n\n"

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
