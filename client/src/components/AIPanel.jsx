import { useState, useEffect, useRef } from 'react'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'

const ContentRenderer = ({ blocks }) => {
  // Group consecutive table blocks into complete tables
  const groupedBlocks = groupTableBlocks(blocks)

  const renderBlock = (block) => {
    const { type, content, metadata, context } = block

    switch (type) {
      case 'heading_2':
        return (
          <h2 className="text-2xl font-bold text-gray-900 mt-6 mb-4 pb-2 border-b border-gray-200">
            {content.replace(/^## /, '')}
          </h2>
        )

      case 'heading_3':
        return (
          <h3 className="text-xl font-semibold text-gray-800 mt-5 mb-3">
            {content.replace(/^### /, '')}
          </h3>
        )

      case 'paragraph':
        return (
          <p className="text-gray-700 leading-relaxed mb-4">
            <FormattedText content={content} />
          </p>
        )

      case 'code_block':
        const language = metadata?.language || context?.code_language || 'text'
        const codeContent = content.replace(/^```\w*\n?/, '').replace(/```$/, '')
        
        return (
          <div className="my-4 rounded-lg overflow-hidden border border-gray-200">
            <div className="bg-gray-800 text-gray-300 px-4 py-2 text-sm font-mono">
              {language}
            </div>
            <SyntaxHighlighter
              language={language}
              style={vscDarkPlus}
              customStyle={{
                margin: 0,
                padding: '1rem',
                background: '#1e1e1e',
                fontSize: '14px',
                lineHeight: '1.5'
              }}
            >
              {codeContent}
            </SyntaxHighlighter>
          </div>
        )

      case 'table_group':
        return renderStreamingTable(block.tableBlocks)

      case 'numbered_list_item':
        const numberMatch = content.match(/^(\d+)\.\s*(.*)/)
        const number = numberMatch ? numberMatch[1] : '1'
        const listContent = numberMatch ? numberMatch[2] : content
        
        return (
          <div className="flex mb-2">
            <span className="text-blue-600 font-semibold mr-3 mt-0.5 min-w-[1.5rem]">
              {number}.
            </span>
            <div className="flex-1">
              <FormattedText content={listContent} />
            </div>
          </div>
        )

      case 'bulleted_list_item':
        const bulletContent = content.replace(/^\s*\*\s*/, '')
        
        return (
          <div className="flex mb-2 ml-4">
            <span className="text-gray-600 mr-3 mt-1">•</span>
            <div className="flex-1">
              <FormattedText content={bulletContent} />
            </div>
          </div>
        )

      case 'divider':
        return <hr className="my-6 border-gray-300" />

      case 'line_break':
        return <br />

      default:
        return (
          <div className="text-gray-700 mb-2">
            <FormattedText content={content} />
          </div>
        )
    }
  }

  // Function to group consecutive table blocks
  function groupTableBlocks(blocks) {
    const grouped = []
    let currentTableBlocks = []
    
    for (let i = 0; i < blocks.length; i++) {
      const block = blocks[i]
      
      if (block.type === 'table') {
        currentTableBlocks.push(block)
      } else {
        // If we have accumulated table blocks, create a table group
        if (currentTableBlocks.length > 0) {
          grouped.push({
            type: 'table_group',
            tableBlocks: [...currentTableBlocks],
            block_id: `table_group_${grouped.length}`
          })
          currentTableBlocks = []
        }
        // Add non-table block
        grouped.push(block)
      }
    }
    
    // Handle any remaining table blocks
    if (currentTableBlocks.length > 0) {
      grouped.push({
        type: 'table_group',
        tableBlocks: [...currentTableBlocks],
        block_id: `table_group_${grouped.length}`
      })
    }
    
    return grouped
  }

  const renderStreamingTable = (tableBlocks) => {
    if (!tableBlocks || tableBlocks.length === 0) return null

    // Extract headers and rows from the streaming table blocks
    const headers = []
    const rows = []
    
    for (const block of tableBlocks) {
      const { metadata, content } = block
      
      // Skip separator rows (contain only dashes)
      if (content && content.includes('---')) {
        continue
      }
      
      // Parse the markdown table row
      const cells = content
        .replace(/^\|/, '')  // Remove leading pipe
        .replace(/\|$/, '')  // Remove trailing pipe
        .split('|')
        .map(cell => cell.trim())
        .filter(cell => cell !== '')

      if (metadata?.is_header || metadata?.subtype === 'header') {
        headers.push(...cells)
      } else if (cells.length > 0) {
        rows.push(cells)
      }
    }

    // If no headers found, use the first row as headers
    const finalHeaders = headers.length > 0 ? headers : (rows.length > 0 ? rows.shift() : [])
    
    if (finalHeaders.length === 0) return null

    return (
      <div className="my-4 overflow-x-auto">
        <table className="min-w-full border border-gray-300 rounded-lg overflow-hidden">
          <thead className="bg-gray-50">
            <tr>
              {finalHeaders.map((header, index) => (
                <th 
                  key={index}
                  className="px-4 py-3 text-left text-sm font-semibold text-gray-900 border-b border-gray-300"
                >
                  <FormattedText content={header} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex} className="hover:bg-gray-50">
                {row.map((cell, cellIndex) => (
                  <td 
                    key={cellIndex}
                    className="px-4 py-3 text-sm text-gray-700 border-b border-gray-200"
                  >
                    <FormattedText content={cell} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <div className="space-y-1">
      {groupedBlocks.map((block, index) => (
        <div key={`${block.block_id || index}`}>
          {renderBlock(block)}
        </div>
      ))}
    </div>
  )
}

const FormattedText = ({ content }) => {
  const formatText = (text) => {
    return text
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/`([^`]+)`/g, '<code class="bg-gray-100 px-1 py-0.5 rounded text-sm font-mono text-gray-800">$1</code>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
  }

  return (
    <span
      dangerouslySetInnerHTML={{
        __html: formatText(content)
      }}
    />
  )
}

const AIPanel = ({ isOpen, onToggle, onApplyContent }) => {
  const [messages, setMessages] = useState([
    {
      id: 1,
      type: 'assistant',
      content: 'Hello! I\'m your AI assistant. How can I help you with your content today?',
      blocks: []
    },
  ])
  const [inputMessage, setInputMessage] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [lastAIResponse, setLastAIResponse] = useState('')
  const [currentBlocks, setCurrentBlocks] = useState([])
  const [currentBlock, setCurrentBlock] = useState(null)

  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, isLoading])

  const handleSendMessage = async () => {
    if (!inputMessage.trim()) return

    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: inputMessage,
      blocks: []
    }

    setMessages(prev => [...prev, userMessage])
    setInputMessage('')
    setIsLoading(true)
    setCurrentBlocks([])
    setCurrentBlock(null)

    const checkpointId = localStorage.getItem('checkpoint_id')
    const url = checkpointId
      ? `http://localhost:8000/enhanced_chat_stream/${encodeURIComponent(inputMessage)}?checkpoint_id=${checkpointId}`
      : `http://localhost:8000/enhanced_chat_stream/${encodeURIComponent(inputMessage)}`

    const eventSource = new EventSource(url)

    let aiMessage = {
      id: Date.now() + 1,
      type: 'assistant',
      content: '',
      blocks: []
    }

    let accumulatedBlocks = []
    let currentBlockData = null

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data)

      if (data.type === 'checkpoint') {
        localStorage.setItem('checkpoint_id', data.checkpoint_id)
      } else if (data.type === 'block_start') {
        currentBlockData = {
          type: data.block_info.type,
          block_id: data.block_info.block_id,
          content: '',
          metadata: data.block_info.metadata,
          context: {}
        }
      } else if (data.type === 'content') {
        if (currentBlockData) {
          currentBlockData.content += data.content
          currentBlockData.context = data.context
          currentBlockData.metadata = { ...currentBlockData.metadata, ...data.metadata }
        }
        
        aiMessage.content += data.content
        setLastAIResponse(aiMessage.content)
        
        // Update current blocks for real-time display
        const updatedBlocks = [...accumulatedBlocks]
        if (currentBlockData) {
          updatedBlocks.push(currentBlockData)
        }
        
        setCurrentBlocks(updatedBlocks)
        aiMessage.blocks = updatedBlocks
        
        setMessages(prev => {
          const last = prev[prev.length - 1]
          if (last?.id === aiMessage.id) {
            return [...prev.slice(0, -1), { ...aiMessage }]
          }
          return [...prev, { ...aiMessage }]
        })
      } else if (data.type === 'block_end') {
        if (currentBlockData) {
          accumulatedBlocks.push({ ...currentBlockData })
          currentBlockData = null
        }
      } else if (data.type === 'line_break') {
        accumulatedBlocks.push({ type: 'line_break', content: '', block_id: `line_break_${Date.now()}` })
      } else if (data.type === 'end') {
        eventSource.close()
        setIsLoading(false)
        setCurrentBlocks([])
      }
    }

    eventSource.onerror = () => {
      eventSource.close()
      setIsLoading(false)
      setCurrentBlocks([])
      console.error('SSE connection error')
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  if (!isOpen) {
    return (
      <div className="w-12 bg-gray-800 flex items-center justify-center">
        <button
          onClick={onToggle}
          className="p-2 text-white hover:bg-gray-700 rounded"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </button>
      </div>
    )
  }

  return (
    <div className="w-96 bg-[#f9fafb] border-l border-gray-200 flex flex-col h-screen">
      {/* Header */}
      <div className="p-4 border-b bg-white shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-800">AI Assistant</h2>
          <button
            onClick={onToggle}
            className="p-1 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <p className="text-sm text-gray-500 mt-1">Ask anything about your content ✍️</p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-sm px-4 py-3 rounded-xl text-sm shadow-sm ${
                message.type === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-800 border border-gray-200'
              }`}
            >
              {message.type === 'assistant' && message.blocks && message.blocks.length > 0 ? (
                <ContentRenderer blocks={message.blocks} />
              ) : (
                <div className="whitespace-pre-wrap">
                  <FormattedText content={message.content} />
                </div>
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-200 px-4 py-3 rounded-xl text-gray-800 max-w-sm">
              {currentBlocks.length > 0 ? (
                <div>
                  <ContentRenderer blocks={currentBlocks} />
                  <div className="flex space-x-1 mt-2">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                  </div>
                </div>
              ) : (
                <div className="flex space-x-1">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                </div>
              )}
            </div>
          </div>
        )}

        <div ref={messagesEndRef}></div>
      </div>

      {/* Apply Button */}
      {lastAIResponse && (
        <div className="p-4 pt-0 text-right">
          <button
            onClick={() => onApplyContent(lastAIResponse)}
            className="text-sm px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded"
          >
            Apply Changes to Page
          </button>
        </div>
      )}

      {/* Input */}
      <div className="p-4 border-t bg-white">
        <div className="flex space-x-2">
          <textarea
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type a message..."
            rows="1"
            className="flex-1 resize-none px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={isLoading}
          />
          <button
            onClick={handleSendMessage}
            disabled={!inputMessage.trim() || isLoading}
            className="px-4 py-2 rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}

export default AIPanel