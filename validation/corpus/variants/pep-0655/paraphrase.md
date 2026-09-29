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

:pep:`589` provides notation
for declaring a TypedDict in which every key is required and notation for defining
a TypedDict with :pep:`all potentially-missing keys <589#totality>`, but it
offers no way to declare that some keys are required while others
are potentially-missing. Two new notations are introduced by this PEP:
``Required[]``, which may be applied to individual items of a
TypedDict to mark them as required, and
``NotRequired[]``, which may be applied to individual items
to mark them as potentially-missing.

No changes to the Python grammar are made by this PEP. The intent is that correct use
of required and potentially-missing TypedDict keys be
enforced only by static type checkers; Python itself does not need to
enforce it at runtime.


Motivation
==========

Wanting to define a TypedDict where some keys are
required and others are potentially-missing is fairly common. At present, the only way
to define a TypedDict like this is to declare one TypedDict with one value
for ``total`` and then have another TypedDict with a
different value for ``total`` inherit from it:

::

   class _MovieBase(TypedDict):  # implicitly total=True
       title: str

   class Movie(_MovieBase, total=False):
       year: int

It is cumbersome to have to declare two separate TypedDict types to
achieve this.

Two new type qualifiers are introduced by this PEP, ``typing.Required`` and
``typing.NotRequired``, which make it possible to define a *single* TypedDict containing
both required and potentially-missing keys:

::

   class Movie(TypedDict):
       title: str
       year: NotRequired[int]

With this PEP it also becomes possible to define TypedDicts using the
:pep:`alternative functional syntax <589#alternative-syntax>`
that mix required and potentially-missing keys,
which currently cannot be done at all, since the alternative syntax has
no support for inheritance:

::

   Actor = TypedDict('Actor', {
       'name': str,
       # "in" is a keyword, so the functional syntax is necessary
       'in': NotRequired[List[str]],
   })


Rationale
=========

It may seem unusual to propose a notation that puts the emphasis on marking
*required* keys instead of *potentially-missing* keys, which is what is
customary in other languages such as TypeScript:

.. code-block:: typescript

   interface Movie {
       title: string;
       year?: number;  // ? marks potentially-missing keys
   }

The problem is that the most suitable word for marking a potentially-missing
key, ``Optional[]``, already has a use in Python for an entirely
different purpose: marking values that may be either of a given
type or ``None``. Specifically, the following does not work:

::

   class Movie(TypedDict):
       ...
       year: Optional[int]  # means int|None, not potentially-missing!

Trying to mark potentially-missing keys with any synonym of “optional”
(such as ``Missing[]``) would be too close to ``Optional[]``
and would be easily confused with it.

For that reason the decision was made to concentrate instead on a positive-form wording for required keys,
which is simple to spell as ``Required[]``.

Still, people who want to extend a regular
(``total=True``) TypedDict often want to add only a handful of
potentially-missing keys, which calls for a way to mark keys that are
*not* required and potentially-missing, so the
``NotRequired[]`` form is permitted for that case as well.


Specification
=============

To indicate that a variable declared in a TypedDict definition is a required key,
the ``typing.Required`` type qualifier is used:

::

   class Movie(TypedDict, total=False):
       title: Required[str]
       year: int

In addition, to indicate that a variable declared in a TypedDict definition is a
potentially-missing key, the ``typing.NotRequired`` type qualifier is
used:

::

   class Movie(TypedDict):  # implicitly total=True
       title: str
       year: NotRequired[int]

Using ``Required[]`` or ``NotRequired[]`` in any
position other than an item of a TypedDict is an error.
This restriction must be enforced by type checkers.

``Required[]`` and ``NotRequired[]`` may be used even on
items where they are redundant, allowing for extra explicitness when wanted:

::

   class Movie(TypedDict):
       title: Required[str]  # redundant
       year: NotRequired[int]

Using ``Required[]`` and ``NotRequired[]`` together at the
same time is an error:

::

   class Movie(TypedDict):
       title: str
       year: NotRequired[Required[int]]  # ERROR

This restriction must be enforced by type checkers.
The runtime implementations of ``Required[]`` and ``NotRequired[]``
are also permitted to enforce it.

``Required[]`` and ``NotRequired[]`` are also supported by the
:pep:`alternative functional syntax <589#alternative-syntax>`
for TypedDict:

::

   Movie = TypedDict('Movie', {'name': str, 'year': NotRequired[int]})


Interaction with ``total=False``
--------------------------------

A :pep:`589`-style TypedDict declared with ``total=False`` is always equivalent
to a TypedDict with an implicit ``total=True`` definition in which every one of its
keys is marked as ``NotRequired[]``.

So:

::

   class _MovieBase(TypedDict):  # implicitly total=True
       title: str

   class Movie(_MovieBase, total=False):
       year: int


is the same as:

::

   class _MovieBase(TypedDict):
       title: str

   class Movie(_MovieBase):
       year: NotRequired[int]


Interaction with ``Annotated[]``
-----------------------------------

It is possible to use ``Required[]`` and ``NotRequired[]`` together with ``Annotated[]``,
nested in either order:

::

   class Movie(TypedDict):
       title: str
       year: NotRequired[Annotated[int, ValueRange(-9999, 9999)]]  # ok

::

   class Movie(TypedDict):
       title: str
       year: Annotated[NotRequired[int], ValueRange(-9999, 9999)]  # ok

Specifically, permitting ``Annotated[]`` to be the outermost annotation
on an item improves interoperability with uses of annotations unrelated to typing,
which may always want ``Annotated[]`` to be the outermost annotation.
[3]_


Runtime behavior
----------------


Interaction with ``get_type_hints()``
'''''''''''''''''''''''''''''''''''''

When applied to a TypedDict, ``typing.get_type_hints(...)`` will by default
remove any ``Required[]`` or ``NotRequired[]`` type qualifiers,
because these qualifiers are expected to get in the way of code
that introspects type annotations casually.

With ``typing.get_type_hints(..., include_extras=True)``, on the other hand,
``Required[]`` and ``NotRequired[]`` type qualifiers *will* be kept,
for the benefit of advanced code introspecting type annotations that
wants to keep *all* of the annotations from the original source:

::

   class Movie(TypedDict):
       title: str
       year: NotRequired[int]

   assert get_type_hints(Movie) == \
       {'title': str, 'year': int}
   assert get_type_hints(Movie, include_extras=True) == \
       {'title': str, 'year': NotRequired[int]}


Interaction with ``get_origin()`` and ``get_args()``
''''''''''''''''''''''''''''''''''''''''''''''''''''

``typing.get_origin()`` and ``typing.get_args()`` are going to be updated so that they
recognize ``Required[]`` and ``NotRequired[]``:

::

   assert get_origin(Required[int]) is Required
   assert get_args(Required[int]) == (int,)

   assert get_origin(NotRequired[int]) is NotRequired
   assert get_args(NotRequired[int]) == (int,)


Interaction with ``__required_keys__`` and ``__optional_keys__``
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Any item marked with ``Required[]`` always shows up
in the ``__required_keys__`` of the TypedDict that contains it. Likewise any item
marked with ``NotRequired[]`` always shows up in ``__optional_keys__``.

::

   assert Movie.__required_keys__ == frozenset({'title'})
   assert Movie.__optional_keys__ == frozenset({'year'})


Backwards Compatibility
=======================

This PEP introduces no backward incompatible changes.


How to Teach This
=================

For a TypedDict in which most keys are required and a few are
potentially-missing, define one TypedDict in the usual way
(leaving out the ``total`` keyword)
and use ``NotRequired[]`` to mark the few keys that are potentially-missing.

For a TypedDict in which most keys are potentially-missing and a few are
required, define a ``total=False`` TypedDict
and use ``Required[]`` to mark the few keys that are required.

Where some items accept ``None`` as well as a regular value, the
recommendation is to prefer the ``TYPE|None`` notation to
``Optional[TYPE]`` when marking those item values, so as to avoid mixing
``Required[]`` or ``NotRequired[]`` with ``Optional[]``
inside the same TypedDict definition:

Yes:

.. code-block::
   :class: good

   from __future__ import annotations  # for Python 3.7-3.9

   class Dog(TypedDict):
       name: str
       owner: NotRequired[str|None]

Okay (required for Python 3.5.3-3.6):

.. code-block::
   :class: maybe

   class Dog(TypedDict):
       name: str
       owner: 'NotRequired[str|None]'

No:

.. code-block::
   :class: bad

   class Dog(TypedDict):
       name: str
       # ick; avoid using both Optional and NotRequired
       owner: NotRequired[Optional[str]]

Usage in Python <3.11
---------------------

Code that supports Python <3.11 and wants to use ``Required[]`` or
``NotRequired[]`` should use ``typing_extensions.TypedDict`` instead
of ``typing.TypedDict``, because the latter does not understand
``(Not)Required[]``. In particular, the ``__required_keys__`` and
``__optional_keys__`` of the resulting TypedDict type will be wrong:

Yes (Python 3.11+ only):

.. code-block::
   :class: good

   from typing import NotRequired, TypedDict

   class Dog(TypedDict):
       name: str
       owner: NotRequired[str|None]

Yes (Python <3.11 and 3.11+):

.. code-block::
   :class: good

   from __future__ import annotations  # for Python 3.7-3.9

   from typing_extensions import NotRequired, TypedDict  # for Python <3.11 with (Not)Required

   class Dog(TypedDict):
       name: str
       owner: NotRequired[str|None]

No (Python <3.11 and 3.11+):

.. code-block::
   :class: bad

   from typing import TypedDict  # oops: should import from typing_extensions instead
   from typing_extensions import NotRequired

   class Movie(TypedDict):
       title: str
       year: NotRequired[int]

   assert Movie.__required_keys__ == frozenset({'title', 'year'})  # yikes
   assert Movie.__optional_keys__ == frozenset()  # yikes


Reference Implementation
========================

``Required`` and ``NotRequired`` are supported by the
`mypy <http://www.mypy-lang.org/>`__
`0.930 <https://mypy-lang.blogspot.com/2021/12/mypy-0930-released.html>`__,
`pyright <https://github.com/Microsoft/pyright>`__
`1.1.117 <https://github.com/microsoft/pyright/commit/7ed245b1845173090c6404e49912e8cbfb3417c8>`__,
and `pyanalyze <https://github.com/quora/pyanalyze>`__
`0.4.0 <https://pyanalyze.readthedocs.io/en/latest/changelog.html#version-0-4-0-november-18-2021>`__
type checkers.

The
`typing_extensions <https://github.com/python/typing/tree/master/typing_extensions>`__
module provides a reference implementation of the runtime component.


Rejected Ideas
==============

Special syntax around the *key* of a TypedDict item
---------------------------------------------------

::

   class MyThing(TypedDict):
       opt1?: str  # may not exist, but if exists, value is string
       opt2: Optional[str]  # always exists, but may have None value

Changes to the Python grammar would be needed for this notation, and marking
TypedDict items as required or potentially-missing is not thought
to clear the high bar that such grammar changes demand.

::

   class MyThing(TypedDict):
       Optional[opt1]: str  # may not exist, but if exists, value is string
       opt2: Optional[str]  # always exists, but may have None value

With this notation, ``Optional[]`` would mean different things depending
on its position, which is inconsistent and confusing.

In addition, “let’s just not put funny syntax before the colon.” [1]_


Marking required or potentially-missing keys with an operator
-------------------------------------------------------------

Unary ``+`` could serve as shorthand for marking a required key, unary
``-`` for marking a potentially-missing key, or unary ``~`` for marking a key
whose totality is the opposite of normal:

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

Operators like these could be implemented on ``type`` through the ``__pos__``,
``__neg__`` and ``__invert__`` special methods, with no change to the
grammar.

The decision was that introducing the long-form notation first
(that is, ``Required[]`` and ``NotRequired[]``) before introducing
any short-form notation would be the prudent course. This
or other short-form notation options may be reconsidered in future PEPs.

If introducing this short-form notation is reconsidered, note that
``+``, ``-``, and ``~`` already carry meanings in the Python
typing world: covariant, contravariant, and invariant:

::

   >>> from typing import TypeVar
   >>> (TypeVar('T', covariant=True), TypeVar('U', contravariant=True), TypeVar('V'))
   (+T, -U, ~V)


Marking absence of a value with a special constant
--------------------------------------------------

A new type-level constant could be introduced that indicates a value is absent
when it appears as a member of a union, much like JavaScript’s
``undefined`` type, and perhaps named ``Missing``:

::

   class MyThing(TypedDict):
       req1: int
       opt1: str|Missing
       req2: float

A ``Missing`` constant of this kind might also be used in other situations, for example
as the type of a variable that is defined only under some condition:

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

This use of ``...|Missing``, though, which is equivalent to
``Union[..., Missing]``, does not fit well with the usual meaning of a union:
``Union[...]`` always describes the type of a *value* that is
present. Missingness or non-totality, on the other hand, is a property of a
*variable*. Existing precedent for marking properties of a
variable includes ``Final[...]`` and ``ClassVar[...]``, and the
proposal for ``Required[...]`` is in line with these.

Misalignment with how unions are subdivided
'''''''''''''''''''''''''''''''''''''''''''

In addition, using ``Union[..., Missing]`` does not fit the
usual ways in which union values are broken apart: Ordinarily, components of a union type
can be eliminated with ``isinstance`` checks:

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

If ``Union[..., Missing]`` were allowed, however, you would need either to
eliminate the ``Missing`` case using ``hasattr`` for object attributes:

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

or a ``locals()`` check for local variables:

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

or a check by some other means, for instance against ``globals()`` for global
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

Strange and inconsistent. ``Missing`` is not truly a value at all; it is
the absence of a definition, and that absence ought to be handled
specially.

Difficult to implement
''''''''''''''''''''''

According to Eric Traut of the Pyright type checker team,
a ``Union[..., Missing]``-style notation would be
hard to implement. [2]_

Introduces a second null-like value into Python
'''''''''''''''''''''''''''''''''''''''''''''''

Defining a new type-level ``Missing`` constant would come very close to
introducing a new value-level ``Missing`` constant at runtime, which would create
a second null-like runtime value alongside ``None``. Python having two
separate null-like constants (``None`` and ``Missing``) would
be confusing. Plenty of people new to JavaScript already struggle to
tell apart its analogous constants ``null`` and
``undefined``.


Replace Optional with Nullable. Repurpose Optional to mean “optional item”.
---------------------------------------------------------------------------

``Optional[]`` is used too widely to be deprecated, though its use
*may* decline over time in favor of the ``T|None`` notation specified by :pep:`604`.


Change Optional to mean “optional item” in certain contexts instead of “nullable”
---------------------------------------------------------------------------------

One option is a special flag on a TypedDict definition that changes
how ``Optional`` is interpreted inside the TypedDict, so that it means
“optional item” instead of its usual meaning of “nullable”:

::

   class MyThing(TypedDict, optional_as_missing=True):
       req1: int
       opt1: Optional[str]

or:

::

   class MyThing(TypedDict, optional_as_nullable=False):
       req1: int
       opt1: Optional[str]

Users would be further confused by this, since ``Optional[]`` would then
mean something in *some* contexts that differs from what it means in
other contexts, and the flag would be easy to miss.


Various synonyms for “potentially-missing item”
-----------------------------------------------

-  Omittable – easily confused with optional
-  OptionalItem, OptionalKey – two words; easily confused with
   optional
-  MayExist, MissingOk – two words
-  Droppable – too close to Rust’s ``Drop``, whose meaning is
   different
-  Potential – not specific enough
-  Open – sounds like applies to a whole structure rather then to an
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

This document has been placed in the public domain or under the
CC0-1.0-Universal license, whichever is the more permissive.
