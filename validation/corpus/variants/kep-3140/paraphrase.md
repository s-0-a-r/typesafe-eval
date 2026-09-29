# KEP-3140: TimeZone support in CronJob

<!-- toc -->
- [Release Signoff Checklist](#release-signoff-checklist)
- [Summary](#summary)
- [Motivation](#motivation)
  - [Goals](#goals)
  - [Non-Goals](#non-goals)
- [Proposal](#proposal)
  - [Notes/Constraints/Caveats (Optional)](#notesconstraintscaveats-optional)
  - [Risks and Mitigations](#risks-and-mitigations)
- [Design Details](#design-details)
  - [CronJob API](#cronjob-api)
  - [CronJob controller](#cronjob-controller)
  - [Test Plan](#test-plan)
      - [Prerequisite testing updates](#prerequisite-testing-updates)
      - [Unit tests](#unit-tests)
      - [Integration tests](#integration-tests)
      - [e2e tests](#e2e-tests)
  - [Graduation Criteria](#graduation-criteria)
    - [Alpha](#alpha)
    - [Beta](#beta)
    - [GA](#ga)
  - [Upgrade / Downgrade Strategy](#upgrade--downgrade-strategy)
  - [Version Skew Strategy](#version-skew-strategy)
- [Production Readiness Review Questionnaire](#production-readiness-review-questionnaire)
  - [Feature Enablement and Rollback](#feature-enablement-and-rollback)
  - [Rollout, Upgrade and Rollback Planning](#rollout-upgrade-and-rollback-planning)
  - [Monitoring Requirements](#monitoring-requirements)
  - [Dependencies](#dependencies)
  - [Scalability](#scalability)
  - [Troubleshooting](#troubleshooting)
- [Implementation History](#implementation-history)
- [Drawbacks](#drawbacks)
- [Alternatives](#alternatives)
- [Infrastructure Needed (Optional)](#infrastructure-needed-optional)
<!-- /toc -->

## Release Signoff Checklist

Every item tagged (R) has to be done *before the enhancement targets a milestone / release*.

- [x] (R) The enhancement issue is in the release milestone and links to the KEP directory in [kubernetes/enhancements] (not to the first KEP PR)
- [x] (R) The KEP approvers have approved `implementable` as the KEP status
- [x] (R) The design details are documented well enough
- [x] (R) A test plan exists and takes SIG Architecture and SIG Testing input into account (test refactors included)
  - [x] e2e Tests for every Beta API Operation (endpoint)
  - [x] (R) GA e2e tests meet the requirements for [Conformance Tests](https://github.com/kubernetes/community/blob/master/contributors/devel/sig-architecture/conformance-tests.md)
  - [x] (R) GA e2e tests have run for at least two weeks without flakes
- [x] (R) Graduation criteria are defined
  - [x] (R) [every GA Endpoint](https://github.com/kubernetes/community/pull/1806) is exercised by [Conformance Tests](https://github.com/kubernetes/community/blob/master/contributors/devel/sig-architecture/conformance-tests.md)
- [x] (R) The production readiness review is done
- [x] (R) The production readiness review is approved
- [x] The "Implementation History" section is current for the milestone
- [x] Documentation for users has been written in [kubernetes/website], to be published on [kubernetes.io]
- [x] Supporting material, such as further design documents, links to mailing list threads or SIG meetings, related PRs/issues, and release notes

<!--
**Note:** Go through this checklist again, and update it, each time the enhancement is considered for a milestone.
-->

[kubernetes.io]: https://kubernetes.io/
[kubernetes/enhancements]: https://git.k8s.io/enhancements
[kubernetes/kubernetes]: https://git.k8s.io/kubernetes
[kubernetes/website]: https://git.k8s.io/website

## Summary

A CronJob creates Jobs on the schedule its author gives it, but which Time Zone
that schedule is read in depends on where kube-controller-manager happens to run.
This proposal extends the CronJob resource so that a user can set the TimeZone
in which Jobs are created.

## Motivation

Shortly after [CronJob was introduced in kubernetes](https://github.com/kubernetes/kubernetes/pull/11980),
someone [asked for a way to set time zones](https://github.com/kubernetes/kubernetes/issues/47202).
At that point the [answer from SIG-Apps and SIG-Architecture](https://github.com/kubernetes/kubernetes/issues/47202#issuecomment-360820586)
was that the feature would force cluster operators to ship a TimeZone database
by hand, because golang did not include one.
Since [golang 1.15](https://go.dev/doc/go1.15), the `time/tzdata` package can be
embedded in the binary, so an external database is no longer required.
By then most of the attention had moved to [taking CronJob to GA](https://github.com/kubernetes/enhancements/issues/19),
and TimeZone support was postponed once more. CronJob is now fully GA, so the
original request can finally be addressed.

### Goals

- Add a `.spec.timeZone` field that accepts a valid TimeZone name

### Non-Goals


## Proposal

The CronJob resource gets a `.spec.timeZone` field, and the cronjob controller
uses it when it schedules the next Job run. When the field is missing or empty,
the controller keeps doing what it does today: it uses the time zone of the
kube-controller-manager process.

### Notes/Constraints/Caveats (Optional)

Today's mechanism, which stays the default, depends almost entirely on the time
zone of the kube-controller-manager process, and an ordinary user has a hard time
finding out what that is. An explicit time zone field lets CronJob authors make
creating CronJobs easier for their users.

### Risks and Mitigations

- A stale time zone in golang could produce wrong schedule times

Rebuilding kube-controller-manager with a newer golang version fixes this, but
it depends a lot on the go community keeping the time zone database current.

- A stale time zone database on the machine that runs kube-controller-manager

Cluster administrators should always keep their systems up to date.

- A malicious user could create many CronJobs in different time zones that in
fact fire Jobs at exactly the same moment

Cluster administrators should set quotas so that one user cannot create too many
Jobs and CronJobs.


## Design Details

### CronJob API

A new `timeZone` field is added to the CronJob `.spec`. It holds the name of the
time zone to use; the valid names are listed
[in tz database](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).
If the field is missing or empty, the current behavior applies, which uses the
time zone of the kube-controller-manager process.

In the API code this looks like:

```golang

type CronJobSpec struct {

    // The schedule in Cron format, see https://en.wikipedia.org/wiki/Cron.
    Schedule string

    // Time zone for the above schedule
    TimeZone *string

}
```

The value in the `TimeZone` field is checked against the golang timezone database
embedded in the binaries, which makes the `kube-apiserver` and `kube-controller-manager`
binaries about 500kB larger.

### CronJob controller

When the `TimeZone` field is non-nil and non-empty, the CronJob controller uses
it to parse the schedule and to compute the next run time. The time zone also
shows up in `.status.lastSuccessfulTime` and `.status.lastScheduleTime`.
In every other case the controller behaves as it does now.

### Test Plan

[x] I/we understand that the owners of the affected components may ask for
changes to existing tests so that this code is solid enough before the changes
that implement this enhancement are committed.

##### Prerequisite testing updates

1. Add tests that check case insensitive location loading is handled correctly.
   The [beta requirements](#beta) have more details.
2. Add at least integration tests, and optionally e2e tests, that cover TimeZone usage.

##### Unit tests

- `k8s.io/kubernetes/pkg/apis/batch/validation`: `2023-01-18` - `96.0%`
- `k8s.io/kubernetes/pkg/controller/cronjob`: `2023-01-18` - `51.7%`
- `k8s.io/kubernetes/pkg/registry/batch/cronjob`: `2023-01-18` - `56.3%`

##### Integration tests

None.

##### e2e tests

- [CronJob should support timezone](https://github.com/kubernetes/kubernetes/blob/db4c64b1a987675fff7a234e8633f4fd01c69530/test/e2e/apps/cronjob.go#L301): https://storage.googleapis.com/k8s-triage/index.html?sig=apps&test=should%20support%20timezone

### Graduation Criteria

#### Alpha

- The functionality is implemented behind a feature gate:
  - The TimeZone field is added to the API (kube-apiserver)
  - The CronJob controller responds to the new field (kube-controller-manager)

#### Beta

- Fix the problem with case insensitive location loading:
  - Test skipped on MacOS (https://github.com/kubernetes/kubernetes/pull/109218)
  - Golang issue (https://github.com/golang/go/issues/21512)

#### GA

- Add a new condition for when the cronjob controller finds an invalid time zone.

### Upgrade / Downgrade Strategy

- Upgrades

After upgrading from a release without this feature to a release that has `TimeZone`,
users should see no change in behavior. `TimeZone` defaults to nil, which matches
the current behavior, so backwards compatibility is kept.

- Downgrades

After downgrading from a release with this feature to a release without `TimeZone`,
there are a few cases:
  1. If the TimeZone feature gate was on and the user set a TimeZone, Jobs created
  after the downgrade go back to the old behavior, as though no TimeZone had ever
  been set.
  2. If the TimeZone feature gate was on and the user did not set a TimeZone, the
  behavior should not change.
  3. If the TimeZone feature gate was off, the behavior should not change.

In every case, cluster administrators should watch `cronjob_job_creation_skew`,
which reports the skew between the schedule and the actual job creation.

### Version Skew Strategy

The feature has no implications for the node runtime.

## Production Readiness Review Questionnaire

### Feature Enablement and Rollback

###### How can this feature be enabled / disabled in a live cluster?

- [x] Feature gate (also fill in values in `kep.yaml`)
  - Feature gate name: CronJobTimeZone
  - Components depending on the feature gate: kube-apiserver, kube-controller-manager

###### Does enabling the feature change any default behavior?

No. The default behavior stays the same whether or not the feature gate is on.

###### Can the feature be disabled once it has been enabled (i.e. can we roll back the enablement)?

Yes, it can be turned off. What happens then depends on whether the user set
the new field:

1. If the `TimeZone` field had no value, the behavior does not change.
2. If the user had set a valid `TimeZone`, newly created Jobs fire as though the
field had never been set.

###### What happens if we reenable the feature if it was previously rolled back?

The controller begins reading the new field again.

###### Are there any tests for feature enablement/disablement?

Yes. Unit and integration tests cover enabling, disabling and the transitions between them.

### Rollout, Upgrade and Rollback Planning

###### How can a rollout or rollback fail? Can it impact already running workloads?

An upgrade can hit an enable, disable, enable sequence when a lease is taken by
a new kube-controller-manager, then by an old kube-controller-manager, and then
by a new kube-controller-manager again.

###### What specific metrics should inform a rollback?

A rise in `cronjob_job_creation_skew`, which measures how late a job is created
compared with the requested time slot.

###### Were upgrade and rollback tested? Was the upgrade->downgrade->upgrade path tested?

The upgrade->downgrade->upgrade path was tested by hand, and the tests found no issues.

###### Is the rollout accompanied by any deprecations and/or removals of features, APIs, fields of API types, flags, etc.?

No.

### Monitoring Requirements

###### How can an operator determine if the feature is in use by workloads?

TimeZone has no dedicated metric, but operators should watch `cronjob_job_creation_skew`
and make sure the job creation skew does not grow.

###### How can someone using this feature know that it is working for their instance?

- [x] Events
  - Event Reason: `UnknownTimeZone` when the given TimeZone is not valid

###### What are the reasonable SLOs (Service Level Objectives) for the enhancement?

The 99th percentile of cron_job_creation_skew over a day is <= 15s

###### What are the SLIs (Service Level Indicators) an operator can use to determine the health of the service?

- [x] Metrics
  - Metric name: `cronjob_controller_rate_limiter_use`
  - Components exposing the metric: `kube-controller-manager`
  - Metric name: `cron_job_creation_skew`
  - Components exposing the metric: `kube-controller-manager`


###### Are there any missing metrics that would be useful to have to improve observability of this feature?

No.

### Dependencies

###### Does this feature depend on any specific services running in the cluster?

TimeZone support in CronJob uses an external TimeZone package; when that package
is not available, golang's built-in package is used.

- kube-controller-manager and kube-apiserver
  - Usage description:
    The `CronJobTimeZone` feature gate has to be on in both kube-controller-manager
    and kube-apiserver for the feature to work completely.
    - Impact of its outage on the feature:
      The TimeZone functionality of CronJob stops working.
    - Impact of its degraded performance or high-error rates on the feature:
      New Jobs are created late.

- TimeZone package
  - Usage description: TimeZone support in CronJob uses an external TimeZone package;
    when that package is not available, golang's built-in package is used.
    - Impact of its outage on the feature:
      The TimeZone functionality stops working.
    - Impact of its degraded performance or high-error rates on the feature:
      New Jobs are created late.

### Scalability

###### Will enabling / using this feature result in any new API calls?

No new API calls are expected.

###### Will enabling / using this feature result in introducing new API types?

Yes, the CronJob API will have `.spec.timeZone`.

###### Will enabling / using this feature result in any new calls to the cloud provider?

No new calls to the cloud provider are expected.

###### Will enabling / using this feature result in increasing size or count of the existing API objects?

Yes.

- API type(s): CronJob
- Estimated increase in size: a new CronJob spec field of up to 50 bytes.

###### Will enabling / using this feature result in increasing time taken by any operations covered by existing SLIs/SLOs?

Existing SLIs/SLOs are not expected to increase.

###### Will enabling / using this feature result in non-negligible increase of resource usage (CPU, RAM, disk, IO, ...) in any components?

The extra CPU and memory used by kube-controller-manager is negligible, because
schedule parsing already handles a time zone specification today.
We just do not use it yet.

### Troubleshooting

###### How does this feature react if the API server and/or etcd is unavailable?

###### What are other known failure modes?

- Incorrect TimeZone
  - Detection: a CronJob reports `UnknownTimeZone` events.
  - Mitigations: Correct the TimeZone or suspend the CronJob.
  - Diagnostics: Logs that contain the phrase `TimeZone`.
  - Testing: Unit tests check that an invalid TimeZone is handled correctly in
    both the apiserver and the controller, and that the problem is reported to
    the user.
- Job creation problems
  - Detection: the `cron_job_creation_skew` metric goes above the expected 15s per day.
  - Mitigations: Turn off the `CronJobTimeZone` feature gate.
  - Diagnostics: Look at the CronJob controller logs.
  - Testing: Unit tests check that an invalid TimeZone is handled correctly in
    both the apiserver and the controller, and that the problem is reported to
    the user.

###### What steps should be taken if SLOs are not being met to determine the problem?

Where possible, raise the log level of kube-controller-manager and look through
the cronjob controller logs for warnings and errors that could show where the
problem is.

## Implementation History

- *2022-01-14* - Initial KEP draft
- *2022-06-09* - Updated KEP for beta promotion.
- *2023-01-18* - Updated KEP for stable promotion.

## Drawbacks

TimeZone may make things easier for users whose clusters span several TimeZones,
but it adds complexity to the code, and operators have to work out again when a
CronJob will actually create a Job once `.spec.timeZone` is set.

## Alternatives

One alternative was to give the time zone as an offset from UTC, but a name
looks friendlier to users.

## Infrastructure Needed (Optional)

None.
