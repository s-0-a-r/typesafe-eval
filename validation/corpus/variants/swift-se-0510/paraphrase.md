# Introduce `Dictionary.mapKeyedValues`

* Proposal: [SE-0510](0510-dictionary-mapvalues-with-keys.md)
* Authors: [Diana Ma](https://github.com/tayloraswift) (tayloraswift)
* Review Manager: [Steve Canon](https://github.com/stephentyrone)
* Status: **Accepted with modifications**
* Implementation: [`#86268`](https://github.com/swiftlang/swift/pull/86268)
* Review: ([pitch](https://forums.swift.org/t/giving-dictionary-mapvalues-access-to-the-associated-key/83904))
  ([review](https://forums.swift.org/t/se-0510-dictionary-mapvalueswithkeys/84547))
  ([acceptance](https://forums.swift.org/t/accepted-with-modifications-se-0510-dictionary-mapvalueswithkeys/85124))


## Introduction

This proposal adds a method `Dictionary.mapKeyedValues` which supplies the `Key` to the transformation closure.

With it, we can transform dictionary values using the context of their associated keys while avoiding the performance cost of rehashing (or, for `reduce`, reallocating) the dictionary storage, a cost that cannot currently be avoided with `init(uniqueKeysWithValues:)` or `reduce(into:)`.

## Motivation

Today, if the mapped dictionary value has to be computed from the dictionary key, we need to use one of the following:

```swift
let new: [Key: NewValue] = .init(
    uniqueKeysWithValues: old.lazy.map { ($0, transform(id: $0, payload: $1)) }
)
// or
let new: [Key: NewValue] = old.reduce(into: [:]) {
    $0[$1.key] = transform(id: $1.key, payload: $1.value)
}
```

Both of these patterns are heavily pessimized because of costly hashing, though benchmarks often show the first to be slightly “less bad” than the second, since it performs fewer intermediate reallocations.

While users sometimes also want to [transform dictionary keys](https://forums.swift.org/t/mapping-dictionary-keys/15342), this proposal concentrates on the case where dictionary keys are never changed and serve only to supply context (such as aggregation parameters) that is not part of the payload values.

## Proposed solution

I propose that the following methods be added to `Dictionary`:

```swift
extension Dictionary {
    public func mapKeyedValues<T, E>(
        _ transform: (Key, Value) throws(E) -> T
    ) throws(E) -> Dictionary<Key, T>

    public func compactMapKeyedValues<T, E>(
        _ transform: (Key, Value) throws(E) -> T?
    ) throws(E) -> Dictionary<Key, T>
}
```

> [!NOTE]
> The original proposal included `compactMapKeyedValues` only as an alternative considered, because it does not get the same performance benefit that `mapKeyedValues` gets. It is nonetheless a useful operation (even though it can also be written as a reduce), and reviewers considered it valuable to give it a name, so it was added when this proposal was accepted.

### Usage example

```swift
let balances: [Currency: Int64] = [.USD: 13, .EUR: 15]
let displayText: [Currency: String] = balances.mapKeyedValues {
    "\($0.alpha3) balance: \($1)"
}
```

## Detailed design

The implementation would follow the existing `mapValues` method, except that within the storage iteration loop it would hand the key together with the value to the transformation closure.

On Apple platforms, a `Dictionary` can be backed by a Cocoa dictionary. This raises no major problems, since `__CocoaDictionary` can be retrofitted within the standard library with essentially the same machinery as `_NativeDictionary`, and the new `mapKeyedValues` can dispatch between the two in exactly the way the existing `mapValues` does.


## Source compatibility

This change is additive to both the ABI and the API.

## Alternatives considered

### Alternative naming

The first draft of this proposal intended to overload the existing `mapValues` method so that it would accept a closure taking both `Key` and `Value`. It turned out this would break source in rare cases where `mapValues` was called on a dictionary whose value type was a 2-tuple. For that reason, the new name `mapKeyedValues` was selected to avoid source compatibility problems.

### Doing nothing

Being an extensively frozen type, it might be possible for developers to retrofit `Dictionary` in user space to support key context by depending on implementation details that are stable but unspecified. However, this would not be a sound workflow, and we should not encourage it.


## Future directions

### Reassigning the name `mapValues`

We may later want to rename the existing `mapValues` method to something such as `mapValuesWithoutKeys`, which would let the standard library, in a subsequent language mode, reassign the `mapValues` name to the version that provides key context to the transformation closure.

### Changes to `OrderedDictionary` (swift-collections)

Extending this proposal naturally, the `OrderedDictionary` type in the `swift-collections` package might also get a `mapKeyedValues` method that offers similar performance benefits. 

Its signature would be as follows:

```swift
extension OrderedDictionary {
    @inlinable public func mapKeyedValues<T, E>(
        _ transform: (Key, Value) throws(E) -> T
    ) throws(E) -> OrderedDictionary<Key, T>
}
```

For `OrderedDictionary`, the performance gain might be even larger than for `Dictionary`. `OrderedDictionary` keeps a standard `Array` for keys and values, along with a sidecar hash table used for lookups. The existing workaround (`reduce` or `init`) requires rebuilding the whole hash table and eagerly copying the keys array. Instead, we could use zipped iteration to map the underlying `_keys` and `_values` arrays into a new array of values, and then copy the `_keys` table – which includes the hash table `__storage` – and is an O(1) copy-on-write if it is not mutated, or O(*n*) upon later mutation.
