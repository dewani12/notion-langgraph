import { useState } from 'react'
import PageMenu from './components/PageMenu'
import HeroPanel from './components/HeroPanel'
import AIPanel from './components/AIPanel'

const App = () => {
  const [selectedPage, setSelectedPage] = useState(null)
  const [pages, setPages] = useState([
    { id: 1, title: 'Welcome', content: 'Welcome to the Notion!' }
  ])
  const [isRightPanelOpen, setIsRightPanelOpen] = useState(true)

  const addPage = () => {
    const newPage = {
      id: Date.now(),
      title: 'New page',
      content: '',
    }
    setPages([...pages, newPage])
    setSelectedPage(newPage)
  }

  const updatePage = (id, updates) => {
    setPages(pages.map(page =>
      page.id === id ? { ...page, ...updates } : page
    ))

    // If selected page is updated, reflect immediately
    if (selectedPage?.id === id) {
      setSelectedPage(prev => ({ ...prev, ...updates }))
    }
  }

  const handleApplyContent = (newContent) => {
    if (selectedPage) {
      const extractedTitle = extractTitleFromContent(newContent) || selectedPage.title
      updatePage(selectedPage.id, { title: extractedTitle, content: newContent })
    }
  }

  const extractTitleFromContent = (content) => {
    // Looks for a markdown-style title
    const match = content.match(/^## ✍️ (.+)/m)
    return match ? match[1].trim() : null
  }


  return (
    <div className="flex h-screen bg-gray-50">
      {/* Left Panel - Page Creation */}
      <PageMenu
        pages={pages}
        selectedPage={selectedPage}
        onSelectPage={setSelectedPage}
        onAddPage={addPage}
      />

      {/* Center Panel - Content Display */}
      <HeroPanel
        selectedPage={selectedPage}
        onUpdatePage={updatePage}
      />

      {/* Right Panel - AI Chatbot */}
      <AIPanel
        isOpen={isRightPanelOpen}
        onToggle={() => setIsRightPanelOpen(!isRightPanelOpen)}
        onApplyContent={handleApplyContent} // ✅ added
      />
    </div>
  )
}

export default App
