import { useState, useEffect } from 'react'

const HeroPanel = ({ selectedPage, onUpdatePage }) => {
  const [localTitle, setLocalTitle] = useState('')
  const [localContent, setLocalContent] = useState('')

  useEffect(() => {
    if (selectedPage) {
      setLocalTitle(selectedPage.title)
      setLocalContent(selectedPage.content)
    } else {
      setLocalTitle('')
      setLocalContent('')
    }
  }, [selectedPage])

  if (!selectedPage) {
    return (
      <div className="flex-1 flex items-center justify-center bg-white">
        <div className="text-center">
          <svg className="w-16 h-16 mx-auto text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <h2 className="text-xl font-medium text-gray-600 mb-2">Select a page to start writing</h2>
          <p className="text-gray-500">Choose a page from the sidebar or create a new one</p>
        </div>
      </div>
    )
  }

  const handleTitleChange = (e) => setLocalTitle(e.target.value)
  const handleContentChange = (e) => setLocalContent(e.target.value)

  const handleTitleBlur = () => {
    if (selectedPage.title !== localTitle) {
      onUpdatePage(selectedPage.id, { title: localTitle })
    }
  }

  const handleContentBlur = () => {
    if (selectedPage.content !== localContent) {
      onUpdatePage(selectedPage.id, { content: localContent })
    }
  }

  return (
    <div className="flex-1 bg-white flex flex-col">
      {/* Page Header */}
      <div className="border-b border-gray-200 p-6">
        <input
          type="text"
          value={localTitle}
          onChange={handleTitleChange}
          onBlur={handleTitleBlur}
          className="text-3xl font-bold text-gray-900 w-full bg-transparent border-none outline-none focus:ring-0"
          placeholder="Untitled"
        />
      </div>

      {/* Page Content */}
      <div className="flex-1 p-6">
        <textarea
          value={localContent}
          onChange={handleContentChange}
          onBlur={handleContentBlur}
          className="w-full h-full resize-none bg-transparent border-none outline-none focus:ring-0 text-gray-700 text-lg leading-relaxed"
          placeholder="Start writing your content here..."
        />
      </div>
    </div>
  )
}

export default HeroPanel
