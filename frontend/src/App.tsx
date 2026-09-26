import { BrowserRouter, Routes, Route } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Companies from "./pages/Companies";
import CompanyDetail from "./pages/CompanyDetail";
import FinancialData from "./pages/FinancialData";
import FinancialMetrics from "./pages/FinancialMetrics";
import ShariahScreening from "./pages/ShariahScreening";
import Valuation from "./pages/Valuation";
import TechnicalAnalysis from "./pages/TechnicalAnalysis";
import AIInsights from "./pages/AIInsights";
import Layout from "./components/Layout";
import Rankings from "./pages/Rankings";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/companies" element={<Companies />} />
          <Route path="/rankings" element={<Rankings />} />
          <Route path="/companies/:ticker" element={<CompanyDetail />} />
          <Route
            path="/companies/:ticker/financials"
            element={<FinancialData />}
          />
          <Route
            path="/companies/:ticker/metrics"
            element={<FinancialMetrics />}
          />
          <Route
            path="/companies/:ticker/screening"
            element={<ShariahScreening />}
          />
          <Route path="/companies/:ticker/valuation" element={<Valuation />} />
          <Route
            path="/companies/:ticker/technical"
            element={<TechnicalAnalysis />}
          />
          <Route path="/companies/:ticker/ai" element={<AIInsights />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
