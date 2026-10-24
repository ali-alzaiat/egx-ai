import { lazy } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/ui/AppShell";
import CompanyHub from "./components/hub/CompanyHub";
import FinancialsLayout from "./components/hub/FinancialsLayout";
import { LangProvider } from "./i18n/useLang";
import { ThemeProvider } from "./theme/useTheme";

// Route-level code splitting: each page loads on first visit.
const Alerts = lazy(() => import("./pages/Alerts"));
const Companies = lazy(() => import("./pages/Companies"));
const CompanyDetail = lazy(() => import("./pages/CompanyDetail"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Events = lazy(() => import("./pages/Events"));
const FilingsIntake = lazy(() => import("./pages/FilingsIntake"));
const FinancialMetrics = lazy(() => import("./pages/FinancialMetrics"));
const NotFound = lazy(() => import("./pages/NotFound"));
const Peers = lazy(() => import("./pages/Peers"));
const Rankings = lazy(() => import("./pages/Rankings"));
const Ratios = lazy(() => import("./pages/Ratios"));
const Recommendations = lazy(() => import("./pages/Recommendations"));
const Screening = lazy(() => import("./pages/Screening"));
const ShariahScreening = lazy(() => import("./pages/ShariahScreening"));
const Statements = lazy(() => import("./pages/Statements"));
const Watchlists = lazy(() => import("./pages/Watchlists"));
const AdminCompanySection = lazy(() => import("./pages/admin/AdminCompanySection"));
const AdminLayout = lazy(() => import("./pages/admin/AdminLayout"));
const AdminMarket = lazy(() => import("./pages/admin/AdminMarket"));
const PriceTab = lazy(() => import("./components/hub/tabViews").then((m) => ({ default: m.PriceTab })));
const QualityTab = lazy(() => import("./components/hub/tabViews").then((m) => ({ default: m.QualityTab })));
const ThesisTab = lazy(() => import("./components/hub/tabViews").then((m) => ({ default: m.ThesisTab })));
const ValuationTab = lazy(() => import("./components/hub/tabViews").then((m) => ({ default: m.ValuationTab })));

function App() {
  return (
    <LangProvider>
      <ThemeProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/recommendations" element={<Recommendations />} />
              <Route path="/rankings" element={<Rankings />} />
              <Route path="/companies" element={<Companies />} />
              <Route path="/screening" element={<Screening />} />
              <Route path="/watchlists" element={<Watchlists />} />
              <Route path="/alerts" element={<Alerts />} />
              <Route path="/events" element={<Events />} />

              {/* Company hub: one header, seven tabs. Old paths redirect (spec 1.1). */}
              <Route path="/companies/:ticker" element={<CompanyHub />}>
                <Route index element={<CompanyDetail />} />
                <Route path="price" element={<PriceTab />} />
                <Route path="financials" element={<FinancialsLayout />}>
                  <Route index element={<Statements />} />
                  <Route path="ratios" element={<Ratios />} />
                  <Route path="metrics" element={<FinancialMetrics />} />
                  <Route path="quality" element={<QualityTab />} />
                </Route>
                <Route path="valuation" element={<ValuationTab />} />
                <Route path="shariah" element={<ShariahScreening />} />
                <Route path="peers" element={<Peers />} />
                <Route path="thesis" element={<ThesisTab />} />

                <Route path="signals" element={<Navigate to="../price" replace />} />
                <Route path="technical" element={<Navigate to="../price" replace />} />
                <Route path="statements" element={<Navigate to="../financials" replace />} />
                <Route path="ratios" element={<Navigate to="../financials/ratios" replace />} />
                <Route path="metrics" element={<Navigate to="../financials/metrics" replace />} />
                <Route path="score" element={<Navigate to="../valuation#score" replace />} />
                <Route path="screening" element={<Navigate to="../shariah" replace />} />
                <Route path="disclosures" element={<Navigate to="../thesis#filings" replace />} />
                {/* /companies/:ticker/ai was removed (R43 #13): it falls through to Not found. */}
                <Route path="*" element={<NotFound nested />} />
              </Route>

              <Route path="/intake" element={<Navigate to="/admin/intake" replace />} />
              <Route path="/admin" element={<AdminLayout />}>
                <Route path="market" element={<AdminMarket />} />
                <Route path="intake" element={<FilingsIntake />} />
                <Route path="disclosures" element={<AdminCompanySection />} />
                <Route path="peers" element={<AdminCompanySection />} />
                <Route path="thesis" element={<AdminCompanySection />} />
                <Route path="*" element={<NotFound nested />} />
              </Route>

              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ThemeProvider>
    </LangProvider>
  );
}

export default App;
