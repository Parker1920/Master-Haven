/** Catalogue — the wiki portal: every namespace as a tile with live counts. */
import { CataloguePortal } from "../components/CataloguePortal";
import { useAuth } from "../hooks/useAuth";

export function Catalogue() {
  const { user } = useAuth();
  const canCreate = !!user && (user.base_role !== "reader" || user.is_admin);
  return (
    <>
      <div className="ta-cat-head">
        <h2 className="ta-cat-head-title">The Catalogue</h2>
        <p className="ta-cat-head-sub">
          Everything in the multiverse, documented by the people who found it.
          Pick a category to browse{canCreate ? ", or add a page" : ""}.
        </p>
        {canCreate && (
          <a href="#/new-article" className="ta-btn ta-btn-primary" style={{ marginTop: 12, display: "inline-block" }}>
            + Create a page
          </a>
        )}
      </div>
      <CataloguePortal />
    </>
  );
}
