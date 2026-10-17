import { useParams } from "react-router-dom";
import CompanyTabs from "../components/CompanyTabs";
import { useRatios } from "../api/client";

export default function Ratios() {
  const { ticker } = useParams();
  const t = ticker ?? "";
  const { data, isLoading, error } = useRatios(t);

  return (
    <div className="page">
      <CompanyTabs ticker={t} />
      <h1>Ratios</h1>
      {isLoading && <p>Loading…</p>}
      {error && <p>Failed to load ratios.</p>}
      <table>
        <tbody>
          {data?.map((r) => (
            <tr key={r.code}>
              <td>{r.code}</td>
              <td>{r.value ?? "—"}</td>
              <td>{r.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
