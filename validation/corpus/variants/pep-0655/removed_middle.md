PEP: 655
Title: Marking individual TypedDict items as required or potentially-missing
Author: David Foster <david at dafoster.net>
Sponsor: Guido van Rossum <guido at python.org>
Discussions-To: https://mail.python.org/archives/list/typing-sig@python.org/thread/53XVOD5ZUKJ263MWA6AUPEA6J7LBBLNV/
Status: Final
Type: Standards Track
Topic: Typing
Created: 30-Jan-2021
Python-Version: 3.11
Post-History: 31-Jan-2021, 11-Feb-2021, 20-Feb-2021, 26-Feb-2021, 17-Jan-2022, 28-Jan-2022
Resolution: https://mail.python.org/archives/list/python-dev@python.org/message/AJEDNVC3FXM5QXNNW5CR4UCT4KI5XVUE/

.. canonical-typing-spec:: :ref:`typing:required-notrequired`,
                           :py:data:`typing.Required` and
                           :py:data:`typing.NotRequired`

Abstract
========

:pep:`589` defines notation
for declaring a TypedDict with all required keys and notation for defining
a TypedDict with :pep:`all potentially-missing keys <589#totality>`, however it
does not provide a mechanism to declare some keys as required and others
as potentially-missing. This PEP introduces two new notations:
``Required[]``, which can be used on individual items of a
TypedDict to mark them as required, and
``NotRequired[]``, which can be used on individual items
to mark them as potentially-missing.

This PEP makes no Python grammar changes. Correct usage
of required and potentially-missing keys of TypedDicts is intended to be
enforced only by static type checkers and need not be enforced by
Python itself at runtime.

Motivation
==========

It is not uncommon to want to define a TypedDict with some keys that are
required and others that are potentially-missing. Currently the only way
to define such a TypedDict is to declare one TypedDict with one value
for ``total`` and then inherit it from another TypedDict with a
different value for ``total``:

::

   class _MovieBase(TypedDict):  # implicitly total=True
       title: str

   class Movie(_MovieBase, total=False):
       year: int

Having to declare two different TypedDict types for this purpose is
cumbersome.

This PEP introduces two new type qualifiers, ``typing.Required`` and
``typing.NotRequired``, which allow defining a *single* TypedDict with
a mix of both required and potentially-missing keys:

::

   class Movie(TypedDict):
       title: str
       year: NotRequired[int]

This PEP also makes it possible to define TypedDicts in the
:pep:`alternative functional syntax <589#alternative-syntax>`
with a mix of required and potentially-missing keys,
which is not currently possible at all because the alternative syntax does
not support inheritance:

::

   Actor = TypedDict('Actor', {
       'name': str,
       # "in" is a keyword, so the functional syntax is necessary
       'in': NotRequired[List[str]],
   })

Rationale
=========

One might think it unusual to propose notation that prioritizes marking
*required* keys rather than *potentially-missing* keys, as is
customary in other languages like TypeScript:

.. code-block:: typescript

   interface Movie {
       title: string;
       year?: number;  // ? marks potentially-missing keys
   }

The difficulty is that the best word for marking a potentially-missing
key, ``Optional[]``, is already used in Python for a completely
different purpose: marking values that could be either of a particular
type or ``None``. In particular the following does not work:

::

   class Movie(TypedDict):
       ...
       year: Optional[int]  # means int|None, not potentially-missing!

Attempting to use any synonym of “optional” to mark potentially-missing
keys (like ``Missing[]``) would be too similar to ``Optional[]``
and be easy to confuse with it.

Thus it was decided to focus on positive-form phrasing for required keys
instead, which is straightforward to spell as ``Required[]``.

Nevertheless it is common for folks wanting to extend a regular
(``total=True``) TypedDict to only want to add a small number of
potentially-missing keys, which necessitates a way to mark keys that are
*not* required and potentially-missing, and so we also allow the
``NotRequired[]`` form for that case.

Specification
=============

The ``typing.Required`` type qualifier is used to indicate that a
variable declared in a TypedDict definition is a required key:

::

   class Movie(TypedDict, total=False):
       title: Required[str]
       year: int

Additionally the ``typing.NotRequired`` type qualifier is used to
indicate that a variable declared in a TypedDict definition is a
potentially-missing key:

::

   class Movie(TypedDict):  # implicitly total=True
       title: str
       year: NotRequired[int]

It is an error to use ``Required[]`` or ``NotRequired[]`` in any
location that is not an item of a TypedDict.
Type checkers must enforce this restriction.

It is valid to use ``Required[]`` and ``NotRequired[]`` even for
items where it is redundant, to enable additional explicitness if desired:

::

   class Movie(TypedDict):
       title: Required[str]  # redundant
       year: NotRequired[int]

It is an error to use both ``Required[]`` and ``NotRequired[]`` at the
same time:

::

   class Movie(TypedDict):
       title: str
       year: NotRequired[Required[int]]  # ERROR

Type checkers must enforce this restriction.
The runtime implementations of ``Required[]`` and ``NotRequired[]``
may also enforce this restriction.

The :pep:`alternative functional syntax <589#alternative-syntax>`
for TypedDict also supports
``Required[]`` and ``NotRequired[]``:

::

   Movie = TypedDict('Movie', {'name': str, 'year': NotRequired[int]})

Interaction with ``total=False``
--------------------------------

Any :pep:`589`-style TypedDict declared with ``total=False`` is equivalent
to a TypedDict with an implicit ``total=True`` definition with all of its
keys marked as ``NotRequired[]``.

Therefore:

::

   class _MovieBase(TypedDict):  # implicitly total=True
       title: str

   class Movie(_MovieBase, total=False):
       year: int

is equivalent to:

::

   class _MovieBase(TypedDict):
       title: str

   class Movie(_MovieBase):
       year: NotRequired[int]

Interaction with ``Annotated[]``
-----------------------------------

``Required[]`` and ``NotRequired[]`` can be used with ``Annotated[]``,
in any nesting order:

::

   class Movie(TypedDict):
       title: str
       year: NotRequired[Annotated[int, ValueRange(-9999, 9999)]]  # ok

::

   class Movie(TypedDict):
       title: str
       year: Annotated[NotRequired[int], ValueRange(-9999, 9999)]  # ok

We could use unary ``+`` as shorthand to mark a required key, unary
``-`` to mark a potentially-missing key, or unary ``~`` to mark a key
with opposite-of-normal totality:

::

   class MyThing(TypedDict, total=False):
       req1: +int    # + means a required key, or Required[]
       opt1: str
       req2: +float

   class MyThing(TypedDict):
       req1: int
       opt1: -str    # - means a potentially-missing key, or NotRequired[]
       req2: float

   class MyThing(TypedDict):
       req1: int
       opt1: ~str    # ~ means a opposite-of-normal-totality key
       req2: float

Such operators could be implemented on ``type`` via the ``__pos__``,
``__neg__`` and ``__invert__`` special methods without modifying the
grammar.

It was decided that it would be prudent to introduce long-form notation
(i.e. ``Required[]`` and ``NotRequired[]``) before introducing
any short-form notation. Future PEPs may reconsider introducing this
or other short-form notation options.

Note when reconsidering introducing this short-form notation that
``+``, ``-``, and ``~`` already have existing meanings in the Python
typing world: covariant, contravariant, and invariant:

::

   >>> from typing import TypeVar
   >>> (TypeVar('T', covariant=True), TypeVar('U', contravariant=True), TypeVar('V'))
   (+T, -U, ~V)

Marking absence of a value with a special constant
--------------------------------------------------

We could introduce a new type-level constant which signals the absence
of a value when used as a union member, similar to JavaScript’s
``undefined`` type, perhaps called ``Missing``:

::

   class MyThing(TypedDict):
       req1: int
       opt1: str|Missing
       req2: float

Such a ``Missing`` constant could also be used for other scenarios such
as the type of a variable which is only conditionally defined:

::

   class MyClass:
       attr: int|Missing

       def __init__(self, set_attr: bool) -> None:
           if set_attr:
               self.attr = 10

::

   def foo(set_attr: bool) -> None:
       if set_attr:
           attr = 10
       reveal_type(attr)  # int|Missing

Misalignment with how unions apply to values
''''''''''''''''''''''''''''''''''''''''''''

However this use of ``...|Missing``, equivalent to
``Union[..., Missing]``, doesn’t align well with what a union normally
means: ``Union[...]`` always describes the type of a *value* that is
present. By contrast missingness or non-totality is a property of a
*variable* instead. Current precedent for marking properties of a
variable include ``Final[...]`` and ``ClassVar[...]``, which the
proposal for ``Required[...]`` is aligned with.

Misalignment with how unions are subdivided
'''''''''''''''''''''''''''''''''''''''''''

Furthermore the use of ``Union[..., Missing]`` doesn’t align with the
usual ways that union values are broken down: Normally you can eliminate
components of a union type using ``isinstance`` checks:

::

   class Packet:
       data: Union[str, bytes]

   def send_data(packet: Packet) -> None:
       if isinstance(packet.data, str):
           reveal_type(packet.data)  # str
           packet_bytes = packet.data.encode('utf-8')
       else:
           reveal_type(packet.data)  # bytes
           packet_bytes = packet.data
       socket.send(packet_bytes)

However if we were to allow ``Union[..., Missing]`` you’d either have to
eliminate the ``Missing`` case with ``hasattr`` for object attributes:

::

   class Packet:
       data: Union[str, Missing]

   def send_data(packet: Packet) -> None:
       if hasattr(packet, 'data'):
           reveal_type(packet.data)  # str
           packet_bytes = packet.data.encode('utf-8')
       else:
           reveal_type(packet.data)  # Missing? error?
           packet_bytes = b''
       socket.send(packet_bytes)

or a check against ``locals()`` for local variables:

::

   def send_data(packet_data: Optional[str]) -> None:
       packet_bytes: Union[str, Missing]
       if packet_data is not None:
           packet_bytes = packet.data.encode('utf-8')

       if 'packet_bytes' in locals():
           reveal_type(packet_bytes)  # bytes
           socket.send(packet_bytes)
       else:
           reveal_type(packet_bytes)  # Missing? error?

or a check via other means, such as against ``globals()`` for global
variables:

::

   warning: Union[str, Missing]
   import sys
   if sys.version_info < (3, 6):
       warning = 'Your version of Python is unsupported!'

   if 'warning' in globals():
       reveal_type(warning)  # str
       print(warning)
   else:
       reveal_type(warning)  # Missing? error?

Weird and inconsistent. ``Missing`` is not really a value at all; it’s
an absence of definition and such an absence should be treated
specially.

Difficult to implement
''''''''''''''''''''''

Eric Traut from the Pyright type checker team has stated that
implementing a ``Union[..., Missing]``-style notation would be
difficult. [2]_

Introduces a second null-like value into Python
'''''''''''''''''''''''''''''''''''''''''''''''

Defining a new ``Missing`` type-level constant would be very close to
introducing a new ``Missing`` value-level constant at runtime, creating
a second null-like runtime value in addition to ``None``. Having two
different null-like constants in Python (``None`` and ``Missing``) would
be confusing. Many newcomers to JavaScript already have difficulty
distinguishing between its analogous constants ``null`` and
``undefined``.

Replace Optional with Nullable. Repurpose Optional to mean “optional item”.
---------------------------------------------------------------------------

``Optional[]`` is too ubiquitous to deprecate, although use of it
*may* fade over time in favor of the ``T|None`` notation specified by :pep:`604`.

Change Optional to mean “optional item” in certain contexts instead of “nullable”
---------------------------------------------------------------------------------

Consider the use of a special flag on a TypedDict definition to alter
the interpretation of ``Optional`` inside the TypedDict to mean
“optional item” rather than its usual meaning of “nullable”:

::

   class MyThing(TypedDict, optional_as_missing=True):
       req1: int
       opt1: Optional[str]

or:

::

   class MyThing(TypedDict, optional_as_nullable=False):
       req1: int
       opt1: Optional[str]

This would add more confusion for users because it would mean that in
*some* contexts the meaning of ``Optional[]`` is different than in
other contexts, and it would be easy to overlook the flag.

Various synonyms for “potentially-missing item”
-----------------------------------------------

-  Omittable – too easy to confuse with optional
-  OptionalItem, OptionalKey – two words; too easy to confuse with
   optional
-  MayExist, MissingOk – two words
-  Droppable – too similar to Rust’s ``Drop``, which means something
   different
-  Potential – too vague
-  Open – sounds like applies to an entire structure rather then to an
   item
-  Excludable
-  Checked

References
==========

.. [1] https://mail.python.org/archives/list/typing-sig@python.org/message/4I3GPIWDUKV6GUCHDMORGUGRE4F4SXGR/

.. [2] https://mail.python.org/archives/list/typing-sig@python.org/message/S2VJSVG6WCIWPBZ54BOJPG56KXVSLZK6/

.. [3] https://bugs.python.org/issue46491

Copyright
=========

This document is placed in the public domain or under the
CC0-1.0-Universal license, whichever is more permissive.