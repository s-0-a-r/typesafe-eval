# Move thumbnail generation to an async job queue

Today, when a host uploads a photo of their space, the API server resizes it into four thumbnail sizes inside the upload request. This document proposes moving that work to background workers.

## Goal

Uploads of large photos (over 10 MB) take 6–9 seconds at p95 because the request waits for all four resizes to finish, and about 2% of them time out at the load balancer's 10-second limit. Hosts then retry, which doubles the load. The goal is to return the upload response as soon as the original file is stored, and generate thumbnails afterwards.

## Non-goals

- Changing the thumbnail sizes or image formats. WebP support is a separate project.
- Reprocessing existing photos. Only new uploads go through the queue.
- Replacing the image library. We keep the current libvips binding.

## Risks

- **Thumbnails missing right after upload.** The listing page may show a photo before its thumbnail exists. Mitigation: the page falls back to a scaled-down original until the job finishes, usually within 3 seconds.
- **Queue backlog during traffic spikes.** Mitigation: autoscale workers on queue depth, and alert when the oldest job is older than 60 seconds.
- **Jobs failing silently.** Mitigation: failed jobs retry three times, then go to a dead-letter queue that pages the on-call engineer.

## Rollback

The upload handler keeps the synchronous code path behind the feature flag `async_thumbnails`. Turning the flag off sends new uploads back through the old path within one minute, with no deploy. Jobs already in the queue keep running, so no photo is left without thumbnails.

## Success metrics

- p95 upload response time under 1.5 seconds for files over 10 MB (today 6–9 seconds).
- Upload timeouts below 0.1% (today about 2%).
- 99% of thumbnails available within 10 seconds of upload.

## Migration plan

1. Deploy the workers and the queue with the flag off.
2. Turn the flag on for internal test accounts and check the metrics for two days.
3. Enable it for 10% of hosts, then 50%, then 100%, one week apart, stopping if any metric regresses.
4. After four weeks at 100%, remove the synchronous code path.

## Impact

- **Search indexing team.** Their indexer reads thumbnail URLs at upload time; it needs to handle a missing thumbnail and pick it up on the next crawl.
- **Mobile app.** The upload screen currently waits for thumbnails before showing a preview; it will show the local image instead.
- **Infrastructure team.** A new queue and a worker pool to run and monitor.

## Open questions

- Should failed thumbnails be retried from the admin screen, or is the dead-letter queue enough?
- Do we need to keep the job history for audit, and if so for how long?

## Owner and timeline

Owner: the listings backend team (lead: Sato). Workers and queue by the end of October, staged rollout through November, cleanup of the old path in December.
