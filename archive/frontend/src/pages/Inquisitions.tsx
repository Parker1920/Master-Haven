/** Inquisitions index. */
import { useEffect, useState } from "react";
import { api, InquisitionSummary } from "../api/client";
import { InquisitionCard } from "../components/InquisitionCard";
import { Loading } from "../components/Loading";
import { useAuth } from "../hooks/useAuth";

export function Inquisitions() {
  const { user } = useAuth();
  const [inqs, setInqs] = useState<InquisitionSummary[] | null>(null);
  useEffect(() => {
    api<InquisitionSummary[]>("/inquisitions").then(setInqs).catch(() => setInqs([]));
  }, []);

  const canInquisition = !!user && (user.base_role === "historian" || user.is_admin);

  return (
    <>
      <div className="ta-civ-index-header">
        <h2 className="ta-civ-index-title">Inquisitions</h2>
        <p className="ta-civ-index-sub">
          {inqs === null ? "Loading…" : `${inqs.length} inquisitions · long-form historical investigations by the Archivists`}
        </p>
      </div>
      {inqs === null ? (
        <Loading />
      ) : inqs.length === 0 ? (
        <div className="ta-empty">
          No inquisitions have been opened yet.
          {canInquisition ? (
            <div className="ta-empty-cta-row">
              <a href="#/compose/inquisition" className="ta-btn ta-btn-primary">+ Begin an inquisition</a>
            </div>
          ) : (
            <p style={{ marginTop: 12, fontSize: 12 }}>
              Inquisitions are opened by Archivist historians.
            </p>
          )}
        </div>
      ) : (
        <div className="ta-inq-shelf" style={{ borderTop: "1px solid var(--ta-border)" }}>
          {inqs.map((i) => <InquisitionCard key={i.id} inq={i} />)}
        </div>
      )}
    </>
  );
}
