import { Link } from "react-router-dom";
import { ChevronIcon } from "../ui/icons";

/** Text link with the mirrored chevron: "Price & signals →" (spec 6.6). */
export default function SectionLink({ to, children }: { to: string; children: string }) {
  return (
    <Link to={to} className="section-link">
      {children}
      <ChevronIcon size={14} />
    </Link>
  );
}
