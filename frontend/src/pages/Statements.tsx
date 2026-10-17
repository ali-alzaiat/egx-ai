import { useParams } from "react-router-dom";
import CompanyTabs from "../components/CompanyTabs";
import { useStatements } from "../api/client";
import type { PeriodStatements, StatementLineRead } from "../types";

export default function Statements() {
  const { ticker } = useParams();
  const t = ticker ?? "";
  const { data, isLoading, error } = useStatements(t);

  return (
    <div className="page">
      <CompanyTabs ticker={t} />
      <h1>Statements</h1>
      {isLoading && <p>Loading…</p>}
      {error && <p>Failed to load statements.</p>}
      {data?.periods.map((p: PeriodStatements) => (
        <section key={p.period_id}>
          <h2>
            {p.period_type} {p.fiscal_year}
          </h2>
          <table>
            <tbody>
              {p.income.map((l: StatementLineRead) => (
                <tr key={l.ontology_code}>
                  <td>{l.label_en}</td>
                  <td>{l.value ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
    </div>
  );
}
