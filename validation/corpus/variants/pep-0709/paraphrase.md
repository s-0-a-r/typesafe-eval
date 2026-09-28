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

At present, comprehensions get compiled as nested functions; this isolates the
comprehension's iteration variable, but it is inefficient at runtime. This PEP
proposes that list, dictionary, and set comprehensions be inlined into the code
where they are defined, with the expected isolation provided by pushing/popping
clashing locals on the stack. The change makes comprehensions a great deal
faster: as much as 2x faster in a microbenchmark of a comprehension alone, which
translates to an 11% speedup in one sample benchmark derived from real-world
code that uses comprehensions heavily while doing actual work.


Motivation
==========

Comprehensions are a feature of the Python language that is popular and used
widely. Compiling comprehensions as nested functions favors simplicity in the
compiler at the cost of performance in user code. Near-identical semantics (see
`Backwards Compatibility`_) can be provided with much better runtime
performance for everyone who uses comprehensions, at the price of only a small
increase in the complexity of the compiler.


Rationale
=========

In many languages, inlining is a common compiler optimization.  In Python,
generalized compile-time inlining of function calls is near-impossible, because
call targets may be patched at runtime. Comprehensions are a special case: the
compiler statically knows the call target, and that target can neither be
patched (barring undocumented and unsupported fiddling directly with bytecode)
nor escape.

Inlining additionally lets other bytecode optimizations in the compiler be more
effective, since they are now able to "see through" the comprehension bytecode
rather than facing an opaque call.

A performance improvement would not normally need a PEP. Here, though, the
simplest and most efficient implementation has some effects visible to users,
so this is more than a performance improvement; it is a (small) change to the
language.


Specification
=============

Given a simple comprehension::

  def f(lst):
      return [x for x in lst]

For the function ``f``, the compiler currently emits this bytecode:

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

The comprehension's bytecode lives in a separate code object. On every call to
``f()``, a new function object meant for a single use is allocated (by
``MAKE_FUNCTION``), called (which allocates and then destroys a new frame on the
Python stack), and then discarded right away.

With this PEP, the compiler will instead emit the following bytecode for
``f()``:

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

A separate code object no longer exists, no single-use function object is
created, and a Python frame no longer has to be created and destroyed.

The ``x`` iteration variable is isolated through a combination of two things:
the new ``LOAD_FAST_AND_CLEAR`` opcode at offset ``6``, which puts any outer
value of ``x`` on the stack before the comprehension runs, and ``30
STORE_FAST``, which puts back the outer value of ``x`` (if there is one) once
the comprehension has run.

When the comprehension accesses variables from the outer scope, inlining means
these variables do not have to be placed in a cell, so the comprehension (along
with all other code in the outer function) can instead access them as ordinary
fast locals. Further performance gains come from this.

Sometimes, in the outer scope, the comprehension iteration variable may be a
global or cellvar or freevar instead of a simple function local. For these
cases, the compiler also pushes and pops the variable's scope information
internally on entering/leaving the comprehension, so the semantics are
preserved. As an example, if the variable is a global outside the
comprehension, ``LOAD_GLOBAL`` will continue to be used where it is referenced
outside the comprehension, while ``LOAD_FAST`` / ``STORE_FAST`` will be used
inside it. If it is a cellvar/freevar outside the comprehension, the
``LOAD_FAST_AND_CLEAR`` / ``STORE_FAST`` that save/restore it stay the same
(no ``LOAD_DEREF_AND_CLEAR`` exists), which means the whole cell (and not only
the value inside it) is saved/restored, and so the comprehension does not write
to the outer cell.

Comprehensions that occur in module or class scope are inlined as well. Here,
the comprehension will bring in the use of fast-locals (``LOAD_FAST`` /
``STORE_FAST``) for the comprehension iteration variable only inside the
comprehension, in a scope that would otherwise use only ``LOAD_NAME`` /
``STORE_NAME``, so isolation is maintained.

Effectively, comprehensions introduce a sub-scope in which local variables are
completely isolated, yet without the performance cost or stack frame entry that
a call involves.

In the reference implementation of this PEP, generator expressions are
currently not inlined. Some generator expressions may be inlined in the future,
in cases where the returned generator object does not leak.

Asynchronous comprehensions get inlined in the same way as synchronous ones; they
need no special handling.


Backwards Compatibility
=======================

Inlining comprehensions will bring about the visible behavior changes listed
below. Adapting to these changes in the implementation required no changes in
the standard library or test suite, which suggests the impact on user code will
probably be minimal.

Specialized tools that rely on undocumented details of the compiler's bytecode
output may of course be affected in ways beyond those below, but such tools
already have to adapt to bytecode changes in every Python version.

locals() includes outer variables
---------------------------------

A call to ``locals()`` inside a comprehension will include every local of the
function that contains the comprehension. For instance, given this function::

  def f(lst):
      return [locals() for x in lst]

In current Python, calling ``f([1])`` returns::

  [{'.0': <list_iterator object at 0x7f8d37170460>, 'x': 1}]

in which ``.0`` is an internal implementation detail: the synthetic, single
argument to the comprehension "function".

With this PEP, it will return this instead::

  [{'lst': [1], 'x': 1}]

The outer ``lst`` variable is now included as a local, and the synthetic
``.0`` is gone.

No comprehension frame in tracebacks
------------------------------------

With this PEP, a comprehension will stop having a dedicated frame of its own in
a stack trace. For instance, given this function::

  def g():
      raise RuntimeError("boom")

  def f():
      return [g() for x in [1]]

At present, a call to ``f()`` produces this traceback:

.. code-block:: text

   Traceback (most recent call last):
     File "<stdin>", line 1, in <module>
     File "<stdin>", line 5, in f
     File "<stdin>", line 5, in <listcomp>
     File "<stdin>", line 2, in g
   RuntimeError: boom

Observe the dedicated frame for ``<listcomp>``.

With this PEP, the traceback instead looks like this:

.. code-block:: text

   Traceback (most recent call last):
     File "<stdin>", line 1, in <module>
     File "<stdin>", line 5, in f
     File "<stdin>", line 2, in g
   RuntimeError: boom

The list comprehension no longer has an extra frame. However, the frame of the
``f`` function carries the correct line number for the comprehension, so the
traceback just becomes more compact, and no useful information is lost.

In theory, code that uses warnings with the ``stacklevel`` argument could see a
behavior change because of the change in the frame stack. In practice, though,
this appears unlikely. It would take a warning raised in library code that is
always called via a comprehension in that same library, with the warning using
a ``stacklevel`` of 3+ to skip past the comprehension and the function
containing it and point at a calling frame outside the library. In a scenario
like that, it would typically be simpler and more reliable to raise the warning
nearer to the calling code and skip fewer frames.

Tracing/profiling will no longer show a call/return for the comprehension
-------------------------------------------------------------------------

Of course, because list/dict/set comprehensions will stop being implemented as
a call to a nested function, tracing/profiling with ``sys.settrace`` or
``sys.setprofile`` will likewise stop reflecting that a call and return took
place.


Impact on other Python implementations
======================================

According to comments from representatives of `GraalPython
<https://discuss.python.org/t/pep-709-inlined-comprehensions/24240/20>`_ and
`PyPy <https://discuss.python.org/t/pep-709-inlined-comprehensions/24240/22>`_,
they would probably feel they had to adapt to the observable behavior changes
here, since it is likely that someone, at some point, will rely on them.
So, all else being equal, fewer observable changes would mean less work. Still,
these changes (at least for GraalPython) should be manageable "without much
headache".


How to Teach This
=================

That comprehension syntax will or should lead to a nested function being
created and called is not intuitively obvious. For new users who are not yet
used to the previous behavior, my guess is that the new behavior in this PEP
will be more intuitive and need less explanation. ("Why does my traceback have
a ``<listcomp>`` line when I never defined a function like that? What is this
``.0`` variable showing up in ``locals()``?")


Security Implications
=====================

None known.


Reference Implementation
========================

A reference implementation of this PEP exists in the form of `a PR against the CPython main
branch <https://github.com/python/cpython/pull/101441>`_ that passes all tests.

On the micro-benchmark ``./python -m pyperf
timeit -s 'l = [1]' '[x for x in l]'``, the reference implementation is 1.96x faster than the ``main`` branch (in a
build compiled with ``--enable-optimizations``.)

On the ``comprehensions`` benchmark in the
`pyperformance <https://github.com/python/pyperformance>`_ benchmark suite
(which is not a micro-benchmark of comprehensions by themselves, but tests
code derived from the real world that does realistic work with comprehensions),
the reference implementation is 11% faster than the ``main`` branch (again in
optimized builds). The other benchmarks in pyperformance (none of them heavy
users of comprehensions) show no impact beyond the noise.

Code without comprehensions is not affected by the implementation.


Rejected Ideas
==============

More efficient comprehension calling, without inlining
------------------------------------------------------

An `alternate approach <https://github.com/python/cpython/pull/101310>`_
adds a new opcode that "calls" a comprehension in a streamlined way, with no
need to create a throwaway function object, though it still creates a new
Python frame. It avoids every one of the visible effects listed under `Backwards
Compatibility`_, and gives about half of the performance benefit (a 1.5x
improvement on the microbenchmark and a 4% improvement on the ``comprehensions``
benchmark in pyperformance.) It also needs a new pointer added to the
``_PyInterpreterFrame`` struct and a new ``Py_INCREF`` on every frame
construction, which means that (unlike this PEP) it carries a (very small)
performance cost for all code. It also leaves less room for future
optimizations.

The position of this PEP is that full inlining provides enough additional
performance to more than justify the behavior changes.


Copyright
=========

This document is placed in the public domain or under the
CC0-1.0-Universal license, whichever is more permissive.
