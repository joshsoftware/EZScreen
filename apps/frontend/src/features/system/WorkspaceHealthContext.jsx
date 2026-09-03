import { createContext, useContext } from 'react'
import { useWorkspaceHealth } from './useWorkspaceHealth'

const WorkspaceHealthContext = createContext(null)

export function WorkspaceHealthProvider({ children, pollMs }) {
  const value = useWorkspaceHealth(pollMs)
  return (
    <WorkspaceHealthContext.Provider value={value}>
      {children}
    </WorkspaceHealthContext.Provider>
  )
}

export function useWorkspaceHealthContext() {
  const context = useContext(WorkspaceHealthContext)
  if (!context) {
    throw new Error('useWorkspaceHealthContext must be used within WorkspaceHealthProvider')
  }
  return context
}
