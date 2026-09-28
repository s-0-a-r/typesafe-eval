PEP: 709
Title: Inlined comprehensions
Author: Carl Meyer <carl@oddbird.net>
Sponsor: Guido van Rossum <guido@python.org>
Discussions-To: https://discuss.python.org/t/pep-709-inlined-comprehensions/24240
Status: Final
Type: Standards Track
Created: 24-Feb-2023
Python-Version: 3.12
Post-History: `25-Feb-2023 <https://discuss.python.org/t/pep-709-inlined-comprehensions/24240>`__
Resolution: https://discuss.python.org/t/pep-709-inlined-comprehensions/24240/36

Abstract
========

Comprehensions are currently compiled as nested functions, which provides
isolation of the comprehension's iteration variable, but is inefficient at
runtime. This PEP proposes to inline list, dictionary, and set comprehensions
into the code where they are defined, and provide the expected isolation by
pushing/popping clashing locals on the stack. This change makes comprehensions
much faster: up to 2x faster for a microbenchmark of a comprehension alone,
translating to an 11% speedup for one sample benchmark derived from real-world
code that makes heavy use of comprehensions in the context of doing actual work.

Motivation
==========

Comprehensions are a popular and widely-used feature of the Python language.
The nested-function compilation of comprehensions optimizes for compiler
simplicity at the expense of performance of user code. It is possible to
provide near-identical semantics (see `Backwards Compatibility`_) with much
better runtime performance for all users of comprehensions, with only a small
increase in compiler complexity.

Rationale
=========

Inlining is a common compiler optimization in many languages.  Generalized
inlining of function calls at compile time in Python is near-impossible, since
call targets may be patched at runtime. Comprehensions are a special case,
where we have a call target known statically in the compiler that can neither
be patched (barring undocumented and unsupported fiddling with bytecode
directly) nor escape.

Inlining also permits other compiler optimizations of bytecode to be more
effective, because they can now "see through" the comprehension bytecode,
instead of it being an opaque call.

Normally a performance improvement would not require a PEP. In this case, the
simplest and most efficient implementation results in some user-visible effects,
so this is not just a performance improvement, it is a (small) change to the
language.

Specification
=============

Given a simple comprehension::

  def f(lst):
      return [x for x in lst]

The compiler currently emits the following bytecode for the function ``f``:

.. code-block:: text

   1           0 RESUME                   0

   2           2 LOAD_CONST               1 (<code object <listcomp> at 0x...)
               4 MAKE_FUNCTION            0
               6 LOAD_FAST                0 (lst)
               8 GET_ITER
              10 CALL                     0
              20 RETURN_VALUE

   Disassembly of <code object <listcomp> at 0x...>:
   2           0 RESUME                   0
               2 BUILD_LIST               0
               4 LOAD_FAST                0 (.0)
         >>    6 FOR_ITER                 4 (to 18)
              10 STORE_FAST               1 (x)
              12 LOAD_FAST                1 (x)
              14 LIST_APPEND              2
              16 JUMP_BACKWARD            6 (to 6)
         >>   18 END_FOR
              20 RETURN_VALUE

The bytecode for the comprehension is in a separate code object. Each time
``f()`` is called, a new single-use function object is allocated (by
``MAKE_FUNCTION``), called (allocating and then destroying a new frame on the
Python stack), and then immediately thrown away.

Under this PEP, the compiler will emit the following bytecode for ``f()``
instead:

.. code-block:: text

  1           0 RESUME                   0

  2           2 LOAD_FAST                0 (lst)
              4 GET_ITER
              6 LOAD_FAST_AND_CLEAR      1 (x)
              8 SWAP                     2
             10 BUILD_LIST               0
             12 SWAP                     2
        >>   14 FOR_ITER                 4 (to 26)
             18 STORE_FAST               1 (x)
             20 LOAD_FAST                1 (x)
             22 LIST_APPEND              2
             24 JUMP_BACKWARD            6 (to 14)
        >>   26 END_FOR
             28 SWAP                     2
             30 STORE_FAST               1 (x)
             32 RETURN_VALUE

There is no longer a separate code object, nor creation of a single-use function
object, nor any need to create and destroy a Python frame.

Isolation of the ``x`` iteration variable is achieved by the combination of the
new ``LOAD_FAST_AND_CLEAR`` opcode at offset ``6``, which saves any outer value
of ``x`` on the stack before running the comprehension, and ``30 STORE_FAST``,
which restores the outer value of ``x`` (if any) after running the
comprehension.

Note the dedicated frame for ``<listcomp>``.

Under this PEP, the traceback looks like this instead:

.. code-block:: text

   Traceback (most recent call last):
     File "<stdin>", line 1, in <module>
     File "<stdin>", line 5, in f
     File "<stdin>", line 2, in g
   RuntimeError: boom

There is no longer an extra frame for the list comprehension. The frame for the
``f`` function has the correct line number for the comprehension, however, so
this simply makes the traceback more compact without losing any useful
information.

It is theoretically possible that code using warnings with the ``stacklevel``
argument could observe a behavior change due to the frame stack change. In
practice, however, this seems unlikely. It would require a warning raised in
library code that is always called through a comprehension in that same
library, where the warning is using a ``stacklevel`` of 3+ to bypass the
comprehension and its containing function and point to a calling frame outside
the library. In such a scenario it would usually be simpler and more reliable
to raise the warning closer to the calling code and bypass fewer frames.

Tracing/profiling will no longer show a call/return for the comprehension
-------------------------------------------------------------------------

Naturally, since list/dict/set comprehensions will no longer be implemented as a
call to a nested function, tracing/profiling using ``sys.settrace`` or
``sys.setprofile`` will also no longer reflect that a call and return have
occurred.

Impact on other Python implementations
======================================

Per comments from representatives of `GraalPython
<https://discuss.python.org/t/pep-709-inlined-comprehensions/24240/20>`_ and
`PyPy <https://discuss.python.org/t/pep-709-inlined-comprehensions/24240/22>`_,
they would likely feel the need to adapt to the observable behavior changes
here, given the likelihood that someone, at some point, will depend on them.
Thus, all else equal, fewer observable changes would be less work. But these
changes (at least in the case of GraalPython) should be manageable "without much
headache".

How to Teach This
=================

It is not intuitively obvious that comprehension syntax will or should result
in creation and call of a nested function. For new users not already accustomed
to the prior behavior, I suspect the new behavior in this PEP will be more
intuitive and require less explanation. ("Why is there a ``<listcomp>`` line in
my traceback when I didn't define any such function? What is this ``.0``
variable I see in ``locals()``?")

Security Implications
=====================

None known.

Reference Implementation
========================

This PEP has a reference implementation in the form of `a PR against the CPython main
branch <https://github.com/python/cpython/pull/101441>`_ which passes all tests.

The reference implementation performs the micro-benchmark ``./python -m pyperf
timeit -s 'l = [1]' '[x for x in l]'`` 1.96x faster than the ``main`` branch (in a
build compiled with ``--enable-optimizations``.)

The reference implementation performs the ``comprehensions`` benchmark in the
`pyperformance <https://github.com/python/pyperformance>`_ benchmark suite
(which is not a micro-benchmark of comprehensions alone, but tests
real-world-derived code doing realistic work using comprehensions) 11% faster
than ``main`` branch (again in optimized builds). Other benchmarks in
pyperformance (none of which use comprehensions heavily) don't show any impact
outside the noise.

The implementation has no impact on non-comprehension code.

Rejected Ideas
==============

More efficient comprehension calling, without inlining
------------------------------------------------------

An `alternate approach <https://github.com/python/cpython/pull/101310>`_
introduces a new opcode for "calling" a comprehension in streamlined fashion
without the need to create a throwaway function object, but still creating a new
Python frame. This avoids all of the visible effects listed under `Backwards
Compatibility`_, and provides roughly half of the performance benefit (1.5x
improvement on the microbenchmark, 4% improvement on ``comprehensions``
benchmark in pyperformance.) It also requires adding a new pointer to the
``_PyInterpreterFrame`` struct and a new ``Py_INCREF`` on each frame
construction, meaning (unlike this PEP) it has a (very small) performance cost
for all code. It also provides less scope for future optimizations.

This PEP takes the position that full inlining offers sufficient additional
performance to more than justify the behavior changes.

Copyright
=========

This document is placed in the public domain or under the
CC0-1.0-Universal license, whichever is more permissive.