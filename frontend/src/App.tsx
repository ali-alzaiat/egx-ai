import { BrowserRouter, Routes, Route } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Companies from "./pages/Companies";
import Recommendations from "./pages/Recommendations";
import CompanyDetail from "./pages/CompanyDetail";
import FinancialData from "./pages/FinancialData";
import FinancialMetrics from "./pages/FinancialMetrics";
import ShariahScreening from "./pages/ShariahScreening";
import Valuation from "./pages/Valuation";
import TechnicalAnalysis from "./pages/TechnicalAnalysis";
import AIInsights from "./pages/AIInsights";
import InvestmentScore from "./pages/InvestmentScore";
import Peers from "./pages/Peers";
import Thesis from "./pages/Thesis";
import Disclosures from "./pages/Disclosures";
import Signals from "./pages/Signals";
import Statements from "./pages/Statements";
import Ratios from "./pages/Ratios";
import Watchlists from "./pages/Watchlists";
import Alerts from "./pages/Alerts";
import Events from "./pages/Events";
import Layout from "./components/Layout";
import Rankings from "./pages/Rankings";
import Screening from "./pages/Screening";
import { LangProvider } from "./i18n/useLang";

function App() {
  return (
    <LangProvider>
      <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/recommendations" element={<Recommendations />} />
          <Route path="/companies" element={<Companies />} />
          <Route path="/rankings" element={<Rankings />} />
          <Route path="/screening" element={<Screening />} />
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
          <Route path="/companies/:ticker/score" element={<InvestmentScore />} />
          <Route path="/companies/:ticker/peers" element={<Peers />} />
          <Route path="/companies/:ticker/thesis" element={<Thesis />} />
          <Route path="/companies/:ticker/disclosures" element={<Disclosures />} />
          <Route path="/companies/:ticker/signals" element={<Signals />} />
          <Route path="/companies/:ticker/statements" element={<Statements />} />
          <Route path="/companies/:ticker/ratios" element={<Ratios />} />
          <Route path="/watchlists" element={<Watchlists />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/events" element={<Events />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </LangProvider>
  );
}

export default App;


