# Backlog

This file tracks active work for future agents and developers. Implement each
item as a small checkpoint, with direct tests before GUI wiring when possible.

## Work Dependency Map

```mermaid
flowchart TD
    StaleDocs[Reconcile stale docs and comments] --> Listener[Add STM32 response listener]
    Listener --> CompleteFlow[Live COMPLETE stops recording]

    JsonExport[Standard JSON export from run_analysis] --> ReviewGrouping[Group Review outputs by session]
    ReviewGrouping --> ReviewStats[Show JSON-backed Review stats]
    ReviewGrouping --> AnnotatedReview[Browse annotated videos in Review]
    ReviewGrouping --> AutoRefresh[Refresh Review after analysis completes]

    PreviewOverlay[Table-detection overlay during preview] --> TrainingUx[Stronger training setup feedback]

    ReviewStats --> SessionCompare[Session comparison]
    AnnotatedReview --> SessionCompare
    JsonExport --> PlayerMetrics[Player-specific metrics]
    ExternalViewer[Improve external viewer behavior] --> ReviewUx[More reliable Review workflow]
```

Use this diagram as the rough order of work. Items near the top unblock items
below them.

## High Priority

- [ ] Reconcile stale docs/comments about recording and preview placeholders with current real `MjpegRecorder` and `CameraPreviewService` code.
- [ ] Add STM32 response listener so live `COMPLETE` stops recording automatically without sending `STOP`.
- [ ] Make JSON export a standard output of `run_analysis()`.
- [ ] Group Review outputs by session: source recording, annotated video, heatmap, and JSON.

## Medium Priority

- [ ] Show JSON-backed Review stats such as bounce count and placement summary.
- [ ] Add annotated video browsing/opening from Review.
- [ ] Refresh Review automatically after analysis completes.
- [ ] Add table-detection overlay during preview.

## Later

- [ ] Add player-specific metrics.
- [ ] Add session comparison.
- [ ] Improve optional external viewer behavior for Jetson/Docker environments.
