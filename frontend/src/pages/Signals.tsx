import { useParams } from "react-router-dom";
import CompanyTabs from "../components/CompanyTabs";
import { useStance } from "../api/client";

export default function Signals() {
  const { ticker } = useParams();
  const t = ticker ?? "";
  const { data, isLoading, error } = useStance(t);

  return (
    <div className="page">
      <CompanyTabs ticker={t} />
      <h1>Signals</h1>
      {isLoading && <p>Loading…</p>}
      {error && <p>Failed to load stance.</p>}
      {data && (
        <>
          <p>
            {data.stance} (confidence {data.confidence})
          </p>
          <ul>
            {data.limitations.map((l: string, i: number) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
