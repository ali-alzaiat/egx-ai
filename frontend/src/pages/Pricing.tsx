import { Link } from "react-router-dom";
import { useBillingPlans } from "../api/client";

export default function Pricing() {
  const { data, isLoading } = useBillingPlans();
  return (
    <div className="page">
      <h1>Pricing</h1>
      {isLoading && <p>Loading…</p>}
      <div className="pricing-grid">
        {data?.map((p) => (
          <div key={p.id} className="pricing-card">
            <h2>{p.tier}</h2>
            <p>{p.price_egp} EGP</p>
            <pre>{JSON.stringify(p.entitlements)}</pre>
          </div>
        ))}
      </div>
      <Link to="/">Back</Link>
    </div>
  );
}
