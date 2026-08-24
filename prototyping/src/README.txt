============================================================================
README.txt  --  what is in this directory and what to read first
============================================================================


WHAT THIS IS

zlang is an unfinished experimental systems language. The ten documents here
are its first formal write-up, modelled on the Go language specification and
split out of a single design document. The three worked programs --
unified.z, json.z, ecs.z -- are the only evidence about this language that is
not an opinion.

Exactly one of the ten is normative: spec.txt. Everything else, including
rules.txt, is commentary on it.


============================================================================
READING ORDER
============================================================================

WHAT ZLANG IS
    glossary.txt, then spec.txt, then the corpus (unified.z, json.z, ecs.z).
    The glossary names the things; the spec says what they mean; the corpus
    shows them used. Skip the spec's annexes on a first pass.

WHAT TO BUILD NEXT
    issues.txt, then open.txt. issues.txt ranks the work and opens with the
    five that matter most; open.txt is the design log behind the questions
    issues.txt schedules.

WHY IT IS LIKE THAT
    rationale.txt, then core.txt. Every rationale entry names the spec rule
    IDs it argues for, so it can be read forwards or entered from a rule ID
    in spec.txt. core.txt then tests the claim the whole design rests on --
    that module, struct, function, sum, shape and closure are one construct
    -- and reports where the test failed. Both are non-normative; core.txt
    says so of itself in its first line under SCOPE.

IMPLEMENTING A PARSER
    grammar.ebnf first -- it is the whole syntax in one file, 80 productions
    rooted at SourceFile -- then spec.txt LEXICAL ELEMENTS (line 108) and
    EXPRESSIONS (line 970). Read issues.txt Z-01 through Z-05 before writing
    code: they are the five places where the grammar had to invent. Then
    read Z-41 through Z-46, which are what a parser actually built from the
    grammar found, including the two things the grammar cannot fix and the
    reason a clean parse of this corpus proves less than it looks.


============================================================================
THE FILES
============================================================================

spec.txt  1935 lines  --  NORMATIVE. This file alone says what a program
means; everything else in this directory is commentary. "This is the
specification of zlang. It states what a program means." Rules carry dotted
identifiers in brackets at the start of a paragraph -- [bind.ascription.1],
[decl.form.2] -- 162 of them, 159 assigned by the rule inventory and three
assigned by this document, never reused or renamed. Sections run
INTRODUCTION through PROGRAM STRUCTURE, then Annex A (grammar), Annex B
(unchecked behaviour), Annex C (open questions) and COVERAGE, which records
what the document did with its sources.

rationale.txt  1155 lines  --  Commentary. "THE ARGUMENTS, AND NOTHING
ELSE." Thirty-nine entries, R-01 through R-39, grouped by topic, each naming
the spec rule IDs it argues for and the lines of the original it was drawn
from. The last five are CUT FEATURES: things considered and rejected.
Nothing here decides what a program means. spec.txt points here exactly
once, at spec.txt:672, and that pointer is navigational: it says where the
argument for three rules is written, not what those rules mean. It is the
only citation running from the normative document into this one, and it is
marked at both ends. No other should be added.

core.txt  1234 lines  --  Commentary, and NON-NORMATIVE throughout: it
states no rule, retires no issue and constrains no program. "A TEST OF THE
CENTRAL CLAIM, and nothing else." It defines a small core language --
fourteen forms -- and translates every surface declaration form into it, to
test the design's central claim that module, struct, function, procedure,
sum, interface, closure and policy are one construct read differently. The
verdict is that they are not. They are TWO constructs plus one undecided:
the BLOCK, a recursive record, which absorbs six of the eight terms and
needs ten of the fourteen forms; the TAGGED BLOCK, `-> oneof`, which needs
three core forms of its own plus its own eliminator, representation and
stage discipline, and is a second construct; and the FUNCTION, undecided,
because it reduces to the block only if the statement layer supplies an
ordered anonymous result member, and the statement layer is unwritten
(issues.txt Z-01). The eighteen places the translation broke carry ids B-1
through B-18. Where this file and spec.txt disagree, spec.txt wins.

unchecked.txt  870 lines  --  Commentary, but normative in intent: each of
its 49 entries is a promise about absence. Ids are dotted and grouped,
U.1.1 through U.11.3, in five categories (UNCHECKED, UNDIAGNOSED,
UNSPECIFIED, PLATFORM, UNWRITTEN). Indexed one line per entry in spec.txt
Annex B. An UNWRITTEN entry is a defect, not a promise.

open.txt  703 lines  --  Commentary. "WHAT IS STILL UNDECIDED, and nothing
else." Sixteen items, OQ-0 through OQ-15, each carrying a slug such as
`oq.ptr.mutability`, ordered by how much of the language each one blocks
rather than by discovery. Indexed one line per item in spec.txt Annex C and
cited inline there as `>>> [OPEN oq.N]`.

issues.txt  1978 lines  --  Commentary, and the work list. Three earlier
analyses merged into 40 issues, plus six later ones from a parser built out
of grammar.ebnf: 46 issues, Z-01 through Z-46, in five bands: BLOCKING (6),
SOUNDNESS (10), GAP (12), DEFECT (14), CORPUS (4). The bands are no longer
contiguous runs of ids, because an id belongs to the thing and not to the
band. Every issue names which analysis found it and every citation was
re-checked against the corpus. It ends with WHAT THE CORPUS PROVES and
CLAIMS I COULD NOT CONFIRM, which is the list of findings the corpus killed.

grammar.ebnf  514 lines  --  Commentary. The first formal grammar, in the Go
specification's EBNF with `...` for Go's range ellipsis. No identifier
scheme: cite it by production name or by line. Where the sources did not
settle a question it takes a position and says so without arguing for it;
those positions are what issues.txt Z-01 and Z-02 are about. It ends with
two lists it keeps against itself -- KNOWN OVER-ACCEPTANCE, nine programs
that derive and should not, and KNOWN UNDER-ACCEPTANCE, the missing bare
block -- which are issues.txt Z-42, Z-43 and Z-45.

glossary.txt  410 lines  --  Commentary, and the shortest way in. "Read this
before rules.txt. It defines no syntax; it only names things." Terms are
CAPS headings -- BLOCK, MEMBER, BINDER, HOLE, PROJECTION -- so cite by term.
It ends with THE THREE-LINE VERSION.

unified.z (394), json.z (888), ecs.z (1201)  --  The corpus, and the
arbiter. unified.z is the declaration form worked as source; json.z is a
JSON parser; ecs.z is an entity-component-system and a game loop. Cite by
file:line. Where a document and the corpus disagree, the corpus wins.


============================================================================
HOW TO CITE
============================================================================

    a rule            spec.txt [bind.ascription.1]
    an argument       rationale.txt R-17
    a break           core.txt B-10
    a hole            unchecked.txt U.1.1
    a question        open.txt OQ-0        (or spec.txt as `oq.0`)
    an issue          issues.txt Z-04
    syntax            grammar.ebnf SourceFile
    evidence          ecs.z:164-169

B-nn is the newest of the eight schemes in this directory and the only one
added after this file was first written. It names a place where core.txt's
translation of the surface language into a core language broke; there are
eighteen, B-1 through B-18. The eighth scheme, glossary.txt's, is a CAPS
term and so has no row above.

Every scheme above is stable under reordering: an id belongs to the thing,
not to its position, so entries can be regrouped, promoted or demoted
without invalidating a citation. That is why none of them are section
numbers. The Rust Reference and the Ferrocene Language Specification both
adopted stable rule ids for the same reason, and it is the reason C's
`6.5.6p8` -- a paragraph number inside a section number -- is considered a
mistake: renumber the section and every citation in the literature is
silently wrong. Ids here are never reused and never renamed; a retired
entry is kept and marked retired.


============================================================================
STATUS
============================================================================

The language cannot yet be implemented from these documents. That is the
expected state. The documents exist to make the holes countable rather than
to hide them.

spec.txt carries 89 markers of the form [UNSPECIFIED] (47), [CONFLICT] (14),
[INVENTED] (12) and [OPEN oq.N] (16), each beginning a line with `>>>`, so

    grep '>>>' spec.txt

lists every known hole. (It also catches the five lines in the INTRODUCTION
that describe the notation, which is why the raw count is 94.) The tallies
are repeated in the COVERAGE section at the end of spec.txt.

issues.txt ranks 46 issues in five bands, six of them BLOCKING: no statement
or control-flow form is specified anywhere, `[]` has five meanings with no
disambiguation rule, `<` is both comparison and the compile-time bracket,
bodiless-means-hole contradicts the bodiless record, `-> oneof {a, b}` is
specified and cannot be parsed, and the rule since written for `<` is
unvalidated -- the corpus cannot tell it apart from bracket balance alone.
Any one of those stops a parser.

core.txt adds no issues and closes none. It reports eighteen breaks, B-1
through B-18, of which eleven appear to be new and seven restate or
cross-reference something already filed.


============================================================================
THE ORIGINAL
============================================================================

rules.txt (895 lines) is the document all of the above was split out of: the
rules and the NOTEs arguing for them in one file, written against unified.z.
spec.txt and rationale.txt together replace it -- the rules went to the
first, the NOTEs to the second, and the spec's COVERAGE section records what
happened to each of the 249 source paragraphs.

It is retained and it is superseded. Consult it only to check whether the
split lost something. Do not cite it as current. Whether it is eventually
deleted is the author's call, and this file does not make it.
