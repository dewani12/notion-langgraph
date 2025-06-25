import { useState } from 'react'

const PageMenu = ({ pages, selectedPage, onSelectPage, onAddPage }) => {
  return (
    <div className="w-64 bg-white border-r border-gray-200 flex flex-col">
      {/* Add Page Button */}
      <div className="p-4">
        <button
          onClick={onAddPage}
          className="w-full px-4 py-2 text-sm bg-blue-500 text-white rounded-md hover:bg-blue-600 transition-colors flex items-center justify-center space-x-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          <span>New Page</span>
        </button>
      </div>

      {/* Pages List */}
      <div className="flex-1 overflow-y-auto">
        <div className="px-4 py-2">
          <h2 className="text-sm font-medium text-gray-600 mb-2">Pages</h2>
          <div className="space-y-1">
            {pages.map((page) => (
              <button
                key={page.id}
                onClick={() => onSelectPage(page)}
                className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                  selectedPage?.id === page.id
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                <div className="flex items-center space-x-2">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <span className="truncate">{page.title}</span>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export default PageMenu