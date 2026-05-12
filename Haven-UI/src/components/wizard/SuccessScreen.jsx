import React from 'react'
import Button from '../Button'
import WizardPreviewPanel from './WizardPreviewPanel'
import WizardAdvancedPreview from './WizardAdvancedPreview'
import { gradeFromScore } from '../shared/StatTile'

// Wizard v1 post-submit success screen (mockup #v11-post-submit-view 5956,
// v11DoSubmit 10050, v11SubmitAnother 10070).
//
// Replaces the pre-submit pane after a successful submit. Shows:
//   - Success message + submission id
//   - Rank delta (#47 → #44 (+3))    [from leaderboard before/after]
//   - Streak count
//   - Conditional achievement chip (e.g. "First Pirate System")
//   - Card preview (the exact preview the user saw at submit time —
//     easy → portrait WizardPreviewPanel, advanced → landscape banner)
//   - Submit Another (resets but preserves identity)
//   - View Leaderboard
//
// Props:
//   result: {
//     submission_id, system_name, status,
//     rankDelta?, streak?, achievement?,
//     submitted_system?,  // snapshot of the wizard's system state at submit time
//     wizard_flow?,        // 'easy' | 'advanced' — picks which preview to render
//   }
//   onSubmitAnother
//   onViewLeaderboard
//   onViewSystem (only when admin direct save → got a system_id)
export default function SuccessScreen({ result, onSubmitAnother, onViewLeaderboard, onViewSystem }) {
  if (!result) return null
  const isPending = result.status === 'pending' || (result.submission_id && !result.system_id)
  const submittedSystem = result.submitted_system
  const flow = result.wizard_flow
  // Re-derive the grade from the snapshot so the preview matches what the user
  // was looking at when they hit submit.
  const score = submittedSystem?.completeness_score ?? submittedSystem?.is_complete
  const gradeInfo = submittedSystem ? { grade: gradeFromScore(score), percent: score } : null
  const isAdvanced = flow === 'advanced'

  return (
    <div
      className={`rounded-xl p-6 sm:p-8 ${isAdvanced ? 'max-w-5xl' : 'max-w-2xl'} mx-auto text-center`}
      style={{ backgroundColor: 'var(--app-card)', border: '2px solid var(--app-primary)' }}
    >
      <div className="text-5xl mb-3">🎉</div>
      <h2 className="text-2xl font-bold mb-2">
        {isPending ? 'Submitted for Approval' : 'System Saved'}
      </h2>
      <p className="opacity-80 mb-6">
        <span className="font-semibold">{result.system_name || 'Your system'}</span>
        {isPending ? ' is in the review queue.' : ' is live in Haven.'}
      </p>

      {/* M-W3: surface a transient-failure warning (e.g. profile lookup
          5xx'd during submit). Submission still went through, but the
          user should know they may need to claim it later. */}
      {result.warning && (
        <div
          className="mb-6 rounded-lg p-3 text-sm text-left"
          style={{
            backgroundColor: 'rgba(255, 180, 76, 0.12)',
            border: '1px solid var(--app-accent-amber, #ffb44c)',
            color: 'var(--app-accent-amber, #ffb44c)',
          }}
        >
          <strong>Heads up:</strong> {result.warning}
        </div>
      )}

      {/* Replay of the preview card the user saw while filling out the wizard.
          Sticky positioning from the source components is neutralized here
          (no scroll container to track on this screen). */}
      {submittedSystem && (
        <div className="mb-6 text-left">
          <div className="text-[10px] uppercase tracking-widest opacity-60 mb-2 text-center">
            Your Submission Preview
          </div>
          {isAdvanced ? (
            <div style={{ position: 'static' }}>
              <WizardAdvancedPreview system={submittedSystem} gradeInfo={gradeInfo} />
            </div>
          ) : (
            <div className="flex justify-center" style={{ position: 'static' }}>
              <WizardPreviewPanel system={submittedSystem} gradeInfo={gradeInfo} />
            </div>
          )}
        </div>
      )}

      {(result.rankDelta || result.streak || result.achievement) && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6 text-left">
          {result.rankDelta && (
            <Stat label="Rank" value={result.rankDelta} />
          )}
          {typeof result.streak === 'number' && (
            <Stat label="Streak" value={`${result.streak} 🔥`} />
          )}
          {result.achievement && (
            <Stat label="Unlocked" value={`★ ${result.achievement}`} accent />
          )}
        </div>
      )}

      <div className="flex flex-wrap justify-center gap-3">
        <Button onClick={onSubmitAnother}>Submit Another</Button>
        {onViewSystem && result.system_id && (
          <Button variant="ghost" onClick={onViewSystem}>View System</Button>
        )}
        <Button variant="ghost" onClick={onViewLeaderboard}>View Leaderboard</Button>
      </div>

      <p className="text-xs opacity-60 mt-6">
        Identity preserved (community, username, expedition) — just enter the next set of glyphs.
      </p>
    </div>
  )
}

function Stat({ label, value, accent }) {
  return (
    <div
      className="rounded p-3"
      style={{
        backgroundColor: 'var(--app-bg)',
        border: `1px solid ${accent ? 'var(--app-accent-amber)' : 'var(--app-accent-3)'}`,
      }}
    >
      <div className="text-[10px] uppercase tracking-wider opacity-60">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  )
}
