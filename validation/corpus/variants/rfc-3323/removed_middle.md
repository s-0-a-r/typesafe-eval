## Restrictions

- Start Date: 2022-10-09
- RFC PR: [rust-lang/rfcs#3323](https://github.com/rust-lang/rfcs/pull/3323)
- Rust Issue: [rust-lang/rust#105077](https://github.com/rust-lang/rust/issues/105077)

## Summary

You can write `pub impl(crate) trait Foo {}`, which limits the ability to implement the trait to the
crate it is defined in. Similarly, you can write `pub struct Foo(pub mut(crate) u8);` and
`pub struct Foo { pub mut(crate) foo: u8 }`, which limits the ability to mutate the `u8` to `crate`.
Outside of the declared scope, implementing the trait or mutating the field is not allowed. If no
restriction is specified, the ability to implement or mutate is uninhibited.

## Motivation

Currently, a trait being visible (and nameable) in a given location implies that you are able to
implement it. However, this does not mean that you want anyone to implement it. It is reasonable to
want a trait to only be implemented by certain types for a variety of reasons. This is commonly
referred to as a "sealed trait", and is frequently simulated by using a public trait in a private or
restricted module.

Similarly, a field being visible currently implies that you are able to mutate it. Just as with
traits being able to be implemented anywhere, this is not always what is wanted. The semantic
correctness of a field may depend on the value of other fields, for example. This means that making
fields public, while acceptable for read access, is not acceptable for write access. Limiting the
ability to mutate a field to a certain scope is desirable in these situations, while still allowing
read access everywhere else.

## Guide-level explanation

**Restrictions** limit what you are allowed to do with a type. In this sense, visibility is a
restriction! The compiler stops you from using a private type, after all. `#[non_exhaustive]` is
also a restriction, as it requires you to have a wildcard arm in a `match` expression. Both of these
are used on a daily basis by countless Rust programmers.

Restrictions are a powerful tool because the compiler stops you from doing something you are not
allowed to do. If you violate a restriction by using unsafe trickery, such as transmuting a type,
the resulting code is _unsound_.

So why do we need restrictions? In fact, they are incredibly important. Those that have been around
a while will remember a time before `#[non_exhaustive]`. Standard practice at that point in time was
to include a `#[doc(hidden)] __NonExhaustive` variant on `enum`s and a private `non_exhaustive: ()`
field on structs. There are two problems with this approach. First, the variant or field exists!
Yes, that is obvious, but it is worth noting that the user can still match exhaustively. Second, the
dummy variant has to be handled even within the crate that defined it. With the `#[non_exhaustive]`
restriction, this is not the case.

### `impl`-restricted traits

It is very common for a library to want to have a trait that exists _but_ only have it be
implemented for the types they want. It is so common, in fact, that
[there are official guidelines][sealed traits] on how to do this! The pattern is typically referred
to as a "sealed trait". Here is a modified example from the guidelines:

[sealed traits]: https://rust-lang.github.io/api-guidelines/future-proofing.html#sealed-traits-protect-against-downstream-implementations-c-sealed

```rust
/// This trait is sealed and cannot be implemented for types outside this crate.
pub trait Foo: private::Sealed {
    // Methods that the user is allowed to call.
    fn bar();
}

// Implement for some types.
impl Foo for usize {
    fn bar() {}
}

mod private {
    pub trait Sealed {}

    // Implement for those same types, but no others.
    impl Sealed for usize {}
}
```

That is a fair amount of code to say "you cannot implement `Foo`"! This works because it is
permitted to have a public item (`Sealed`) in a private module (`private`). More specifically,
`Sealed` is public, but users in another crate are unable to name the trait. This effectively makes
the trait private, assuming it is not used in other manners. It would be far nicer if you could just
write:

```rust
pub impl(crate) trait Foo {
    fn bar();
}

impl Foo for usize {
    fn bar() {}
}
```

Note that there is neither a `Sealed` trait nor a `private` module here. The ability to implement
`Foo` is restricted by the compiler. It knows this because we used `impl(crate)` — the new syntax
introduced here. Just as `pub` accepts a module path, `impl` does the same. This means that
`impl(super)` and `impl(in path::to::module)` are also valid. Using the `impl` keyword in this
position is a natural extension of the existing visibility syntax. The example above would restrict
the ability to implement the trait to the defining crate. If we used `impl(super)` instead, it would
be restricted to the parent module. If we used `impl(in path::to::module)`, it would be restricted
to the specified module. Any attempt to implement the trait outside of these modules will error. For
example, this code:

```rust
pub mod foo {
    pub mod bar {
        pub(crate) impl(super) trait Foo {}
    }

    // Okay to implement `Foo` here.
    impl bar::Foo for i8 {}
}

impl foo::bar::Foo for u8 {} // Uh oh! We cannot implement `Foo` here.
```

could result in the following error:

```text
error: trait cannot be implemented outside `foo`
  --> $DIR/impl-restriction.rs:13:1
   |
LL |         pub(crate) impl(super) trait Foo {}
   |                    ----------- trait restricted here
...
LL | impl foo::bar::Foo for u8 {}
   | ^^^^^^^^^^^^^^^^^^^^^^^^^

error: aborting due to previous error
```

There are benefits to having this restriction built into the language. First, it expresses the
intent of the author more clearly. Documentation can automatically show that the implementation is
restricted, and the compiler can emit better diagnostics when someone tries to implement `Foo`.
Another benefit is that it is no longer possible to accidentally implement `Sealed` for a type but
not `Foo`. This is a very easy mistake to make, and it is difficult to notice. With the new syntax,
you will only have one trait to worry about.

### `mut`-restricted fields

Have you ever wanted to have read-only fields in Rust? C++, C#, Java, TypeScript, Kotlin, and Swift
all have them in some form or another! In Rust, it is feasible to go one step further and have
fields that are only mutable within a certain module. Said another way, you can mutate it but other
people cannot. This is useful for a number of reasons. For example, you may have a `struct` whose
values are always semantically in a given range. This occurs in `time`:

```rust
pub struct Time {
    hour: u8,
    minute: u8,
    second: u8,
    nanosecond: u32,
}
```

The author of `time` would love to have these fields public. However, they do not want users to be
able to change the values, as that would violate the invariants of the type. As a result they
currently have to keep the fields private and write "getter" methods. What if, instead, they could
add `mut(crate)` to a field, just like `pub(crate)`? This would allow them to write:

#### Where does a mutation occur?

#### `struct` expressions are not allowed

## Reference-level explanation

### Syntax

Using the syntax from [the reference for `struct`s][struct syntax], the change needed to support
`mut` restrictions is quite small.

[struct syntax]: https://doc.rust-lang.org/stable/reference/items/structs.html

```diff
StructField :
   OuterAttribute*
   Visibility?
+  MutRestriction?
   IDENTIFIER : Type

TupleField :
   OuterAttribute*
   Visibility?
+  MutRestriction?
   Type

+MutRestriction :
+   mut ( crate )
+   | mut ( self )
+   | mut ( super )
+   | mut ( in SimplePath )
```

Trait definitions need a similar change to the [syntax for `trait`s][trait syntax] to accommodate
`impl` restrictions.

[trait syntax]: https://doc.rust-lang.org/stable/reference/items/traits.html

```diff
Trait :
   unsafe?
+  ImplRestriction?
   trait IDENTIFIER
   GenericParams? ( : TypeParamBounds? )? WhereClause? {
     InnerAttribute*
     AssociatedItem*
   }

+ImplRestriction :
+   impl ( crate )
+   | impl ( self )
+   | impl ( super )
+   | impl ( in SimplePath )
```

Essentially, `mut` and `impl` have the same syntax as `pub`, just with a different keyword. Using
the keyword without providing a path is not allowed.

### Behavior

The current behavior of `pub` is that `pub` makes something visible within the declared scope. If no
scope is declared (such that it is just `pub`), then the item is visible everywhere. This behavior
is preserved for `impl` and `mut`. When a restriction is used, the behavior is allowed only within
the declared scope. While in most cases the default visibility is private, `pub` is default in some
cases, namely `enum` variants, `enum` fields, and `trait` items. `impl` and `mut` will have a
consistent default: when omitted entirely, the scope is inherited from `pub`. This is both what is
most convenient and is what is required for backwards compatibility with existing code.

When an `ImplRestriction` is present, implementations of the associated trait are only permitted
within the designated path. Any implementation of the trait outside this scope is a compile error.
When a `MutRestriction` is present, mutable uses of the associated field are only permitted within
the designated path. Any mutable use of the field outside the scope is a compile error. Further, a
`struct`, `union`, or `enum` variant containing fields with an associated `MutRestriction` may not
be constructed with `struct` expressions unless all fields are unrestricted in the present scope.
This is the case even if the field is not directly declared, such as when functional record updates
are used.

### "Mutable use" in the compiler

The concept of a "mutable use" [already exists][mutating use method] within the compiler. This
catches all situations that are relevant here, including `ptr::addr_of_mut!`, `&mut`, and direct
assignment to a field, while excluding interior mutability. As such, formal semantics of what
constitutes a "mutable use" are not stated here.

[mutating use method]: https://doc.rust-lang.org/nightly/nightly-rustc/rustc_middle/mir/visit/enum.PlaceContext.html#method.is_mutating_use

### Interaction with `trait` aliases

Trait aliases cannot be implemented. As such, there is no concern about compatibility between the
`impl` restriction and `trait` aliases.

## Drawbacks

- Additional syntax for macros to handle
- More syntax to learn
- While unambiguous to parse, `trait impl(crate) Foo` could be confusing due to its similarity to
  `impl Foo`.

## Alternatives

- `impl` and `mut` restrictions could be attributes, similar to `#[non_exhaustive]`.
  - The proposed syntax could by syntactic sugar for these attributes.
- Visibility could be altered to accept restrictions as a type of parameter, such as
  `pub(crate, mut = self)`. This is not ideal because restrictions are not permitted everywhere
  visibility is. As a result, any errors would have to occur later in the compilation process than
  they would be with the proposed syntax. It would also mean macro authors would be unable to accept
  only syntax that would be valid in a given context. Further, some positions such as `enum`
  variants do not semantically accept a visibility, while they do accept a restriction.
- The current syntax separates the `mut`/`impl` keyword from the scope of the restriction. This
  produces verbose syntax. Many users may want similar restrictions. Could we provide a simpler
  syntax if we provided less flexibility? Would a new keyword or two help? We could choose a syntax
  with less flexibility and verbosity but more simplicity. For instance, `sealed` or `readonly`.

## Prior art

- The [`readonly` crate] simulates immutable fields outside of the defining module. Types with this
  attribute cannot define `Deref`, which can be limiting. Additionally, it applies to all fields and
  within the defining crate. The advantages of native read-only fields relating to borrow checking
  also do not apply when using this crate.
- The `derive-getters` and `getset` crates are derive macros that are used to generate getter
  methods. The latter also has the ability to derive setters. This demonstrates the usefulness of
  reduced syntax for common behavior. Further, `getset` allows explicitly setting the visibility of
  the derived methods. In this manner, it is very similar to the ability to provide a path to the
  `mut` restriction.
- The ability to restrict implementations of a trait can be simulated by a public trait in a private
  module. This has the disadvantage that the trait is no longer nameable by external users,
  preventing its use as a generic bound. Current diagnostics, while technically correct, are
  unhelpful to downstream users.
- Various other languages have read-only fields, including C++, C#, Java, TypeScript, Kotlin, and
  Swift.
- Users of many languages, including Rust, regularly implement read-only fields by providing a
  getter method without a setter method, demonstrating a need for this.

## Unresolved questions

- Should an "unnecessary restriction" lint be introduced? It would fire when the restriction is as
  strict or less strict than the visibility. This warning could also be used for `pub(self)`.
  - Does this necessarily have to be decided as part of this RFC?
- How will restrictions work with `macro_rules!` matchers? There is currently a `vis` matcher, but
  it is likely unwise to add a new matcher for each restriction.
  - The proposed syntax cannot be added to the `vis` matcher, as it does not current restrict the
    tokens that can follow. For this reason, it could break existing code, such as the following
    example.

  ```rust
  macro_rules! foo {
      ($v:vis impl(crate) trait Foo) => {}
  }

  foo!(pub impl(crate) trait Foo);
  ```

  - A `restriction` matcher could work, but restrictions are not the same everywhere.
  - `mut_restriction` and `impl_restriction` are relatively long.
- What is the interaction between stability and restrictions?
  - Suggestion: Visibility is an inherent part of the item; restrictions should be as well. Metadata
    can be added in the future indicating when an item had its restriction lifted, if applicable.
    The design for this is left to the language team as necessary. A decision does _not_ need to be
    made prior to stabilization, as stability attributes are not stable in their own right.
- Should the `in` syntax be permitted for restrictions? Including it is consistent with the existing
  syntax for visibility. Further, the lack of inclusion would lead to continued use of the
  workaround for `impl`. For `mut`, there is no workaround. The syntax is not used often for
  visibility, but it is very useful when it is used.
- Should `struct` expressions be disallowed?
  - Where would it be desirable to prohibit mutability after construction, but still permit
    construction with unchecked values?
- Should a simpler syntax be provided for common cases? For instance, `sealed` or `readonly`. A
  different syntax altogether could be used as well.

## Future possibilities

- Explicitly sealed/exhaustive traits could happen in the future. This has the ability to impact
  coherence, such that other crates could rely on the fact that the list of implementations is
  exhaustive. As traits would default to unsealed, this does not have be decided now.
- Trait items could gain proper visibility and/or restrictions of their own. This would allow
  private and/or defaulted trait items that cannot be overridden.
- Set-once fields could potentially occur in the future. Functionally, this would be "true"
  read-only fields, in that they can be constructed but never mutated. They are not included in this
  proposal as the use case is nor clear, nor is there an immediately obvious syntax to support this.
- The default could be changed in a future edition, such as to make `pub field: Type` be only
  mutable within the module rather than mutable everywhere. This seems unlikely, as it would be an
  incredibly disruptive change, and the benefits would have to be significant.
- Syntax such as `impl(mod)` could be added for clarity as an alternative to `impl(self)`.
- `impl` and `mut` could be usable without a path if deemed necessary. This behavior would be
  identical to omitting the keyword entirely.
- `mut` could be placed on the `struct` or variant itself, which would be equivalent to having the
  same restriction on each field. This would avoid repetition.
- Trait implementations could be restricted to being used within a certain scope.