import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Companies from './pages/Companies'
import CompanyDetail from './pages/CompanyDetail'
import FinancialData from './pages/FinancialData'
import Layout from './components/Layout'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/companies" element={<Companies />} />
          <Route path="/companies/:ticker" element={<CompanyDetail />} />
          <Route path="/companies/:ticker/financials" element={<FinancialData />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
