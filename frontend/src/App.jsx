import React, { useState, useEffect } from 'react'
import './App.css'

const API_BASE = import.meta.env.VITE_API_BASE || ''

const REASONS = [
  { value: '', label: 'All Reasons' },
  { value: 'MISSING_IN_B', label: 'Missing in B' },
  { value: 'ORPHAN_IN_B', label: 'Orphan in B' },
  { value: 'DUPLICATE_IN_B', label: 'Duplicate in B' },
  { value: 'VALUE_MISMATCH', label: 'Value Mismatch' },
  { value: 'LOCATION_MISMATCH', label: 'Location Mismatch' },
  { value: 'DATE_MISMATCH', label: 'Date Mismatch' },
]

export default function App() {
  const [orgs, setOrgs] = useState(['ORG-A', 'ORG-B'])
  const [selectedOrg, setSelectedOrg] = useState('ORG-A')
  const [selectedReason, setSelectedReason] = useState('')
  const [sortField, setSortField] = useState('')
  const [sortOrder, setSortOrder] = useState('asc') // 'asc' or 'desc'
  const [disagreements, setDisagreements] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Fetch available organizations on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/orgs/`)
      .then((res) => {
        if (!res.ok) throw new Error('Failed to fetch organizations')
        return res.json()
      })
      .then((data) => {
        if (data && data.length > 0) {
          setOrgs(data)
          if (!data.includes(selectedOrg)) {
            setSelectedOrg(data[0])
          }
        }
      })
      .catch((err) => {
        console.warn('Could not fetch org list, falling back to defaults:', err)
      })
  }, [])

  // Fetch disagreements when org, reason, or sort changes
  useEffect(() => {
    if (!selectedOrg) return

    setLoading(true)
    setError(null)

    const params = new URLSearchParams()
    params.set('org', selectedOrg)
    if (selectedReason) {
      params.set('reason', selectedReason)
    }
    if (sortField) {
      params.set('sort', sortOrder === 'desc' ? `-${sortField}` : sortField)
    }

    fetch(`${API_BASE}/api/disagreements/?${params.toString()}`)
      .then((res) => {
        if (!res.ok) {
          return res.json().then((errData) => {
            throw new Error(errData.error || `HTTP error ${res.status}`)
          })
        }
        return res.json()
      })
      .then((data) => {
        setDisagreements(data)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message || 'An error occurred while fetching data.')
        setLoading(false)
      })
  }, [selectedOrg, selectedReason, sortField, sortOrder])

  const handleSort = (field) => {
    if (sortField === field) {
      if (sortOrder === 'asc') {
        setSortOrder('desc')
      } else {
        // Reset sort
        setSortField('')
        setSortOrder('asc')
      }
    } else {
      setSortField(field)
      setSortOrder('asc')
    }
  }

  const formatCurrency = (val) => {
    if (val === null || val === undefined || val === '') return '-'
    const num = parseFloat(val)
    if (isNaN(num)) return val
    return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }

  const getReasonBadgeClass = (reason) => {
    switch (reason) {
      case 'MISSING_IN_B':
        return 'badge badge-missing'
      case 'ORPHAN_IN_B':
        return 'badge badge-orphan'
      case 'DUPLICATE_IN_B':
        return 'badge badge-duplicate'
      case 'VALUE_MISMATCH':
        return 'badge badge-mismatch'
      case 'LOCATION_MISMATCH':
        return 'badge badge-location'
      case 'DATE_MISMATCH':
        return 'badge badge-date'
      default:
        return 'badge badge-default'
    }
  }

  return (
    <div className="container">
      <header className="header">
        <div className="header-title-row">
          <h1>DealerOS Ledger Reconciliation</h1>
          <span className="subtitle">System A vs System B Comparison</span>
        </div>

        {/* Controls Toolbar */}
        <div className="toolbar">
          <div className="control-group">
            <label htmlFor="org-select">Tenant (Org):</label>
            <select
              id="org-select"
              value={selectedOrg}
              onChange={(e) => setSelectedOrg(e.target.value)}
              className="select-input"
            >
              {orgs.map((org) => (
                <option key={org} value={org}>
                  {org}
                </option>
              ))}
            </select>
          </div>

          <div className="control-group">
            <label htmlFor="reason-select">Filter by Reason:</label>
            <select
              id="reason-select"
              value={selectedReason}
              onChange={(e) => setSelectedReason(e.target.value)}
              className="select-input"
            >
              {REASONS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </div>

          <div className="stats-badge">
            Disagreements Found: <strong>{disagreements.length}</strong>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="main-content">
        {loading && <div className="status-msg loading">Loading disagreements...</div>}
        {error && <div className="status-msg error">Error: {error}</div>}

        {!loading && !error && disagreements.length === 0 && (
          <div className="status-msg empty">
            No disagreements found for organization <strong>{selectedOrg}</strong>
            {selectedReason ? ` with reason "${selectedReason}"` : ''}.
          </div>
        )}

        {!loading && !error && disagreements.length > 0 && (
          <div className="table-responsive">
            <table className="reconcile-table">
              <thead>
                <tr>
                  <th>Reason</th>
                  <th>Record ID</th>
                  <th>Location</th>
                  <th
                    className="sortable"
                    onClick={() => handleSort('value')}
                    title="Click to sort by value"
                  >
                    System A Value{' '}
                    {sortField === 'value' ? (sortOrder === 'asc' ? '▲' : '▼') : '↕'}
                  </th>
                  <th>System B Value</th>
                  <th
                    className="sortable"
                    onClick={() => handleSort('difference')}
                    title="Click to sort by difference"
                  >
                    Difference{' '}
                    {sortField === 'difference' ? (sortOrder === 'asc' ? '▲' : '▼') : '↕'}
                  </th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {disagreements.map((row, idx) => (
                  <tr key={`${row.record_id}-${row.reason}-${idx}`}>
                    <td>
                      <span className={getReasonBadgeClass(row.reason)}>{row.reason}</span>
                    </td>
                    <td className="code-font">{row.record_id}</td>
                    <td>{row.location || '-'}</td>
                    <td className="num-col">{formatCurrency(row.a_value)}</td>
                    <td className="num-col">{formatCurrency(row.b_value)}</td>
                    <td className="num-col diff-col">{formatCurrency(row.difference)}</td>
                    <td className="details-col">{row.details || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  )
}
