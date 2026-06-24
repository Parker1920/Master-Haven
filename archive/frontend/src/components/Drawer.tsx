/**
 * Drawer — mobile nav slide-out.
 *
 * Sections: Browse / My archive / Editorial / Admin (role-gated).
 * Closes on Escape, traps focus while open, and exposes the
 * role="dialog" semantics so screen readers announce it correctly.
 */

import { useEffect, useRef } from "react";
import { useAuth } from "../hooks/useAuth";

interface Props {
  open: boolean;
  onClose: () => void;
}

export function Drawer({ open, onClose }: Props) {
  const { user } = useAuth();
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    previouslyFocused.current = document.activeElement as HTMLElement | null;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
      if (e.key === "Tab" && dialogRef.current) {
        // Tiny focus-trap: cycle Tab focus inside the dialog.
        const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
          "a[href], button:not([disabled]), [tabindex]:not([tabindex='-1'])"
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        const active = document.activeElement as HTMLElement;
        if (e.shiftKey && active === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && active === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", onKey);
    // Move initial focus into the dialog
    setTimeout(() => {
      const focusable = dialogRef.current?.querySelector<HTMLElement>("a[href], button");
      focusable?.focus();
    }, 0);
    return () => {
      document.removeEventListener("keydown", onKey);
      previouslyFocused.current?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      <div
        onClick={onClose}
        style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", zIndex: 99,
        }}
        aria-hidden="true"
      />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="Main menu"
        style={{
          position: "fixed", top: 0, left: 0, bottom: 0, width: "84%", maxWidth: 320,
          background: "var(--ta-surface)", zIndex: 100, padding: 16,
          overflowY: "auto",
          display: "flex", flexDirection: "column", gap: 16,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ fontFamily: "Georgia, serif", margin: 0 }}>Menu</h3>
          <button
            className="ta-mobile-icon-btn"
            onClick={onClose}
            aria-label="Close menu"
            style={{ fontSize: 20, lineHeight: 1 }}
          >×</button>
        </div>

        <DrawerSection title="Browse">
          <DrawerLink href="#/" onClose={onClose}>Newsroom</DrawerLink>
          <DrawerLink href="#/catalogue" onClose={onClose}>Catalogue</DrawerLink>
          <DrawerLink href="#/civs" onClose={onClose}>Civilizations</DrawerLink>
          <DrawerLink href="#/inquisitions" onClose={onClose}>Inquisitions</DrawerLink>
          <DrawerLink href="#/timeline" onClose={onClose}>Timeline</DrawerLink>
          <DrawerLink href="#/search" onClose={onClose}>Search</DrawerLink>
        </DrawerSection>

        {user && (
          <DrawerSection title="My archive">
            <DrawerLink href="#/dashboard" onClose={onClose}>Dashboard</DrawerLink>
            <DrawerLink href={`#/profile/${user.discord_username}`} onClose={onClose}>My profile</DrawerLink>
            <DrawerLink href="#/watchlist" onClose={onClose}>Watchlist</DrawerLink>
          </DrawerSection>
        )}

        {user && (user.base_role !== "reader" || user.is_admin) && (
          <DrawerSection title="Editorial">
            <DrawerLink href="#/drafts" onClose={onClose}>Drafts</DrawerLink>
            <DrawerLink href="#/compose/brief" onClose={onClose}>+ New brief</DrawerLink>
            <DrawerLink href="#/compose/feature" onClose={onClose}>+ New feature</DrawerLink>
            {(user.base_role === "historian" || user.is_admin) && (
              <DrawerLink href="#/compose/inquisition" onClose={onClose}>+ Begin inquisition</DrawerLink>
            )}
          </DrawerSection>
        )}

        {user?.is_admin && (
          <DrawerSection title="Admin">
            <DrawerLink href="#/admin" onClose={onClose}>Admin panel</DrawerLink>
          </DrawerSection>
        )}

        {!user && (
          <DrawerSection title="">
            <DrawerLink href="#/login" onClose={onClose}>Sign in</DrawerLink>
          </DrawerSection>
        )}
      </div>
    </>
  );
}

function DrawerSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      {title && (
        <div style={{
          fontSize: 10, textTransform: "uppercase", letterSpacing: 1,
          color: "var(--ta-text-faint)", fontWeight: 500, marginBottom: 6,
        }}>{title}</div>
      )}
      <nav style={{ display: "flex", flexDirection: "column", gap: 8 }}>{children}</nav>
    </div>
  );
}

function DrawerLink({ href, onClose, children }: { href: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <a
      href={href}
      onClick={onClose}
      style={{
        fontSize: 14, color: "var(--ta-text)", textDecoration: "none",
        padding: "6px 0",
      }}
    >{children}</a>
  );
}
