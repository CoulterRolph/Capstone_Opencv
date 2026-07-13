# Backlog

This file tracks active work for future agents and developers. Implement each
item as a small checkpoint, with direct tests before GUI wiring when possible.

## Work Dependency Map

```mermaid
flowchart TD
    VerifySession[Verify Training to Analysis to Review end to end] --> StableIdentity[Use one video-derived session JSON identity]
    StableIdentity --> ReliableMerge[Reliable analysis-to-JSON merge]
    ReliableMerge --> AutoRefresh[Refresh Review after analysis completes]
    ReliableMerge --> AnnotatedReview[Browse annotated videos in Review]

    Listener[Add STM32 response listener] --> CompleteFlow[Live COMPLETE stops recording]

    PreviewOverlay[Table-detection overlay during preview] --> TrainingUx[Stronger training setup feedback]

    ReliableMerge --> SessionCompare[Session comparison]
    AnnotatedReview --> SessionCompare
    ReliableMerge --> PlayerMetrics[Player-specific metrics]
```

Use this diagram as the rough order of work. Items near the top unblock items
below them.

## High Priority

- [x] Reconcile system and workflow documentation with the session JSON pipeline.
- [ ] Run Training → Analysis → Review end to end on the Jetson.
- [ ] Give every session one video-derived JSON filename so custom display names cannot break the Analysis merge.
- [ ] Add STM32 response listener so live `COMPLETE` stops recording automatically without sending `STOP`.

## Medium Priority

- [x] Show initial JSON-backed Review stats: bounce count, detection rate, and table status.
- [ ] Add annotated video browsing/opening from Review.
- [ ] Refresh Review automatically after analysis completes.
- [ ] Add table-detection overlay during preview.

## Later

- [ ] Add player-specific metrics.
- [ ] Add session comparison.
- [ ] Improve optional external viewer behavior for Jetson/Docker environments.
